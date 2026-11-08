"""Render all 93 observed slide references and their HRMS application status."""
import argparse
import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--refresh", action="store_true")
args = parser.parse_args()
readings = json.loads((ROOT / "docs/references/project-framework/slide-readings.json").read_text(encoding="utf-8"))
application = yaml.safe_load((ROOT / "specs/slide-application.yaml").read_text(encoding="utf-8"))
registry = yaml.safe_load((ROOT / "specs/artifact-registry.yaml").read_text(encoding="utf-8"))
targets = {r["id"]: r["target"] for r in registry["entries"]}
lookup = {r["number"]: r for r in readings}
if set(lookup) != set(range(1, 94)) or {a["number"] for a in application["applications"]} != set(lookup):
    raise RuntimeError("Every one of the 93 slides must be represented exactly once.")
lines = ["# SLIDE-REVIEW-01 — بررسی و اعمال هر 93 اسلاید", "",
    "منبع: [چارچوب پروژهٔ استاد](https://sadprojectdocs.space-z.ai/). در 2026-11-08 تمام 93 اسلاید به ترتیب خوانده و 23 نمودار مستقل بررسی شدند. [متن مشاهده‌شده](references/project-framework/slide-readings.json) و [منابع نمودار](references/project-framework/diagram-sources.json) حفظ شده‌اند.", "",
    "چارچوب برای HRMS اعمال شده است: بازسازی مستندات موجود، سه Core specification/model، نخستین اصلاح معماری و شواهد واقعی. human review، Gate دانشگاهی، همهٔ NFRها و آزمایش‌های scalability به پایان نرسیده‌اند. جدول، تفاوت کار اجراشده و مورد باز را صریح نشان می‌دهد.", "",
    "وضعیت prepared/modelled/recorded یعنی مدرک آماده است و معمولاً review انسانی باز است؛ implemented/tested فقط به همان بخش گفته‌شده اشاره دارد. linked به معنی کنترل پیوند، نه اثبات سازگاری معنایی است.", "",
    "| اسلاید / عنوان دقیق منبع | تطبیق با HRMS | Artifact | وضعیت |", "|---|---|---|---|"]
for record in application["applications"]:
    n = record["number"]
    slide = lookup[n]
    links = []
    for ident in record["artifacts"]:
        target = targets[ident]
        href = target if target.startswith("https://") else "../" + target
        links.append(f"[{ident}]({href})")
    lines.append(f"| [{n}]({slide['url']}) — {slide['title']} | {record['application']} | {', '.join(links)} | {record['status']} |")
lines += ["", "## تفاوت‌ها و محدودیت منبع", "",
    "اسلاید 25 تفاوت موضوع تیم‌ها را مجاز می‌داند؛ الگوی غذا با domain HR جایگزین شده است. جدول 17 برنامهٔ هفتگی و 53 milestoneهای دو هفته‌ای دارد. Rubric در 19/93، Specification=10٪ و Testing=5٪؛ در 61، Testing=10٪ و دسته‌بندی متفاوت است. [هر دو نسخه](10-final-report/rubric.md) حفظ شده‌اند و نمره برای HR ساخته نشده است.", "",
    "اسلاید 57 TR را برای traceability و TRF را برای AI transformation پیشنهاد می‌کند؛ نمونه‌های دیگر با TR برای AI ناسازگارند، پس convention صریح 57 مبناست. نمونه‌های YAML با decision تکراری در 40/84 به YAMLهای پروژه منتقل نشده‌اند. Diagram/caption بازاستفاده‌شده و اعداد کد/coverage/latency مثال‌ها، شاهد HR نیستند.", "",
    "کد ابتدایی HR پیش از مدل‌های این نوبت وجود داشت. برای CR-01، spec و آزمون قبل اصلاح ثبت شدند؛ بسیاری مدل‌ها reconstruction هستند. TRF-02 با prompt/model/design پیش از کد اجرا شد. [رکورد AI](07-ai-transformation/README.md) این ترتیب را بدون بازنویسی تاریخ توضیح می‌دهد.", "",
    "[گزارش جاری](10-final-report/report.md)، [کارهای باز](10-final-report/remaining-work.md) و [نقشهٔ آزمایش‌های معماری](05-architecture/progressive-experiments.md) مسیر ادامه را مشخص می‌کنند."]
target = ROOT / "docs/project-framework-slide-review.md"
if target.exists() and not args.refresh:
    raise FileExistsError("Review exists; use --refresh only to regenerate the application report.")
target.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("Rendered 93 slide application rows using the observed original URLs and titles.")
