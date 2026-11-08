# حفظ خروجی AI و نسخه‌های پروژه

سوابق Stage 1 در [نسخهٔ تاریخی](history/ai-implementation-stage01.md)، docs/prompts/ و archive قدیمی حفظ شده‌اند. آن‌ها منبع اولیه‌اند؛ رونوشت کامل همهٔ پاسخ‌های AI یا مشارکت دانشجو نیستند.

رکوردهای جدید [TRF-01/TRF-02](07-ai-transformation/README.md) شامل task، prompt واقعی، input، output/diff، validation و review انسانیِ باز هستند. اصلاح clock با prompt/model پیش از تغییر ثبت شد؛ reconstruction بعد از کد قدیمی صریح گزارش شده است.

scripts/save_stage_snapshot.py اکنون --name الزامی دارد و نام موجود را رد می‌کند. فرمان بدون آرگومان دیگر معتبر نیست و archive قدیمی جایگزین نمی‌شود:

```powershell
.\.venv\Scripts\python.exe .\scripts\save_stage_snapshot.py --name hrms-next-baseline --description 'Validated named source baseline'
```

snapshot source شامل code/docs/tests/specs/models و manifest hash است؛ credentials/.env/runtime/venv/raw artifacts را کپی نمی‌کند. metadata baseline در docs/snapshots/ و zip محلی در artifacts/ می‌ماند. evidence امن جدید در docs/08-testing/evidence/ ثبت و raw log/CSV محلی نگهداری می‌شود.

human review، modification و contribution باید فقط با شاهد واقعی وارد log شوند. نمره، تست موفق، screenshot یا stage تاریخی به‌صورت فرضی ساخته نمی‌شود.
