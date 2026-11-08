// انتخاب واحدهای مربوط به شعبه؛ اعتبارسنجی نهایی در سرور انجام می‌شود.
document.querySelectorAll('[data-unit-filter]').forEach((form) => {
  const branch = form.querySelector('[data-branch]');
  const unit = form.querySelector('[data-unit]');
  if (!branch || !unit) return;
  function updateUnits() {
    for (const option of unit.options) {
      if (!option.value) continue;
      const available = !branch.value || option.dataset.branchId === branch.value;
      option.hidden = !available;
      option.disabled = !available;
      if (!available && option.selected) unit.value = '';
    }
  }
  branch.addEventListener('change', updateUnits);
  updateUnits();
});
