"""A disposable PostgreSQL namespace for real database and HTTP tests."""
import re
import uuid
from contextlib import ExitStack
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app import access, main, modules, security
from app.database import Base, database_url


class PostgresSandbox:
    def __init__(self):
        self.schema = "hrms_test_" + uuid.uuid4().hex
        self.owner_engine = create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
        self.engine = None
        self.created = False

    def __enter__(self):
        with self.owner_engine.begin() as connection:
            connection.execute(CreateSchema(self.schema))
        self.created = True
        try:
            url = make_url(database_url).update_query_dict({"options": f"-csearch_path={self.schema}"})
            self.url = url.render_as_string(hide_password=False)
            self.engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
            self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
            Base.metadata.create_all(self.engine)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self.engine is not None:
            self.engine.dispose()
        if self.created:
            if not re.fullmatch(r"hrms_test_[0-9a-f]{32}", self.schema):
                raise RuntimeError("Refusing cleanup outside the namespace created by this test.")
            with self.owner_engine.begin() as connection:
                connection.execute(DropSchema(self.schema, cascade=True))
            self.created = False
        self.owner_engine.dispose()


class PostgresTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.resources = ExitStack()
        cls.sandbox = cls.resources.enter_context(PostgresSandbox())
        cls.factory = cls.sandbox.session_factory
        for module in (main, modules, access):
            cls.resources.enter_context(patch.object(module, "SessionLocal", cls.factory))
        # security imports SessionLocal lazily from database.
        from app import database
        cls.resources.enter_context(patch.object(database, "SessionLocal", cls.factory))
        cls.resources.enter_context(patch.object(main, "engine", cls.sandbox.engine))

    @classmethod
    def tearDownClass(cls):
        cls.resources.close()
        super().tearDownClass()
