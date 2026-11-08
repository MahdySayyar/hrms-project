// بررسی واقعی صفحه‌ها در مرورگر؛ فقط پروندهٔ ساختگی همین بررسی ایجاد و حذف می‌شود.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { chromium } = require(process.env.HRMS_PLAYWRIGHT_PATH || 'playwright');
const root = path.resolve(__dirname, '..');
const env = Object.fromEntries(fs.readFileSync(path.join(root, '.env'), 'utf8').split(/\r?\n/).filter(line => line && !line.startsWith('#')).map(line => { const split = line.indexOf('='); return [line.slice(0, split), line.slice(split + 1)]; }));
const artifacts = path.join(root, 'artifacts', 'screenshots');
fs.mkdirSync(artifacts, { recursive: true });
const checks = [];
let employeeId;
let completed = false;
const code = `BROWSER-${Date.now().toString(36)}`.toUpperCase();
function check(name, result) { checks.push({ check: name, passed: !!result }); if (!result) throw new Error(name); }
(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:8000/login');
    await page.screenshot({ path: path.join(artifacts, 'login-desktop.png'), fullPage: true });
    await page.locator('#username').fill(env.ADMIN_USERNAME);
    await page.locator('#password').fill(env.ADMIN_PASSWORD);
    await Promise.all([page.waitForURL('http://127.0.0.1:8000/'), page.getByRole('button', { name: 'ورود به سامانه', exact: true }).click()]);
    check('browser administrator login and dashboard', await page.getByRole('heading', { name: 'داشبورد منابع انسانی', exact: true }).isVisible());
    await page.screenshot({ path: path.join(artifacts, 'dashboard-desktop.png'), fullPage: true });
    await page.getByRole('link', { name: 'پروندهٔ کارکنان', exact: false }).click();
    check('employee table has ten fictional records', await page.locator('tbody tr').count() === 10);
    await page.screenshot({ path: path.join(artifacts, 'employees-desktop.png'), fullPage: true });
    await page.getByRole('link', { name: 'افزودن کارمند', exact: false }).click();
    await page.locator('#employee_code').fill(code);
    await page.locator('#first_name').fill('مرورگر');
    await page.locator('#last_name').fill('آزمایشی');
    await page.locator('#national_id').fill('9900000077');
    await page.locator('#phone').fill('09000000077');
    await page.locator('#email').fill('browser@example.invalid');
    await page.locator('#hire_date').fill('2025-03-04');
    const branchIds = await page.locator('#branch_id option').evaluateAll(options => options.filter(option => option.value).map(option => option.value));
    await page.locator('#branch_id').selectOption(branchIds[0]);
    let unitIds = await page.locator('#unit_id option').evaluateAll(options => options.filter(option => option.value && !option.disabled).map(option => option.value));
    await page.locator('#unit_id').selectOption(unitIds[0]);
    await page.locator('#branch_id').selectOption(branchIds[1]);
    check('changing branch clears mismatched unit in the browser', await page.locator('#unit_id').inputValue() === '');
    check('unit selector offers only units belonging to selected branch', await page.locator('#unit_id option').evaluateAll((options, branchId) => options.filter(option => option.value && !option.disabled).every(option => option.dataset.branchId === branchId), branchIds[1]));
    await page.locator('#branch_id').selectOption(branchIds[0]);
    unitIds = await page.locator('#unit_id option').evaluateAll(options => options.filter(option => option.value && !option.disabled).map(option => option.value));
    await page.locator('#unit_id').selectOption(unitIds[0]);
    const positionId = await page.locator('#position_id option').evaluateAll(options => options.find(option => option.value).value);
    await page.locator('#position_id').selectOption(positionId);
    await page.locator('#contract_type').selectOption('دائم');
    await page.screenshot({ path: path.join(artifacts, 'employee-form-desktop.png'), fullPage: true });
    await Promise.all([page.waitForURL(/\/employees\/\d+\?saved=1/), page.getByRole('button', { name: 'ثبت کارمند', exact: true }).click()]);
    employeeId = Number(new URL(page.url()).pathname.split('/')[2]);
    check('browser submits employee and shows Persian success message', await page.getByRole('status').textContent().then(text => text.includes('با موفقیت ذخیره شد')));
    await page.getByRole('link', { name: 'ویرایش پرونده', exact: true }).click();
    await page.locator('#first_name').fill('مرورگر ویرایش‌شده');
    await Promise.all([page.waitForURL(/\?saved=1/), page.getByRole('button', { name: 'ذخیرهٔ تغییرات', exact: true }).click()]);
    check('browser employee edit is reflected in detail page', await page.getByRole('heading', { level: 1 }).textContent().then(text => text.includes('مرورگر ویرایش‌شده')));
    await Promise.all([page.waitForURL(/\?changed=1/), page.getByRole('button', { name: 'غیرفعال کردن', exact: true }).click()]);
    check('browser deactivation retains accessible detail page', await page.getByRole('button', { name: 'فعال کردن', exact: true }).isVisible());
    await page.getByRole('button', { name: 'فعال کردن', exact: true }).click();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('http://127.0.0.1:8000/');
    await page.screenshot({ path: path.join(artifacts, 'dashboard-mobile.png'), fullPage: true });
    check('mobile dashboard has no page overflow', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.goto('http://127.0.0.1:8000/employees');
    await page.screenshot({ path: path.join(artifacts, 'employees-mobile.png'), fullPage: true });
    check('mobile employee page contains table overflow within panel', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.goto('http://127.0.0.1:8000/employees/new');
    await page.screenshot({ path: path.join(artifacts, 'employee-form-mobile.png'), fullPage: true });
    check('mobile employee form has no page overflow', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    check('no browser JavaScript errors', errors.length === 0);
    completed = true;
  } finally {
    await browser.close();
    if (employeeId) {
      const cleanup = "import sys; from app.database import SessionLocal,Employee; db=SessionLocal(); row=db.get(Employee,int(sys.argv[1])); assert row and row.employee_code==sys.argv[2]; db.delete(row); db.commit(); db.close()";
      execFileSync(path.join(root, '.venv', 'Scripts', 'python.exe'), ['-c', cleanup, String(employeeId), code], { cwd: root, encoding: 'utf8' });
    }
    fs.writeFileSync(path.join(root, 'artifacts', 'browser-results.json'), JSON.stringify({ browser: 'Google Chrome via Playwright', checks, all_passed: completed && checks.every(item => item.passed) }, null, 2));
  }
  console.log(JSON.stringify({ checks, screenshots: artifacts }, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
