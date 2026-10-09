'use strict';

// The site contains protocol explanations and an arithmetic illustration only.
// It neither requests market data nor simulates investment performance.
const arms = {
  S12: {
    tag: 'Primary control',
    title: 'The baseline tempo.',
    description: 'Rebalance twice a year using 12–1 risk-adjusted momentum. Comparing M12 with this arm isolates the scheduled rebalance frequency within the same model.',
    signal: '12–1 risk-adjusted momentum',
    schedule: 'March / September month-end → next open',
    compare: 'M12 · change frequency only',
  },
  M12: {
    tag: 'Primary comparison',
    title: 'Faster rhythm, same signal.',
    description: 'Rebalance monthly using the same 12–1 momentum signal as S12. This is the cleanest test of whether frequency earns its additional costs.',
    signal: '12–1 risk-adjusted momentum',
    schedule: 'Every month-end → next open',
    compare: 'S12 · change frequency only',
  },
  SMIX: {
    tag: 'Replication control',
    title: 'A broader lens, a slower rhythm.',
    description: 'Blend long, medium, and shorter momentum horizons while retaining semiannual rebalancing. This is the control for the second frequency comparison.',
    signal: '50% 12–1 + 30% 6–1 + 20% 3–1',
    schedule: 'March / September month-end → next open',
    compare: 'MMIX · change frequency only',
  },
  MMIX: {
    tag: 'Replication comparison',
    title: 'Does the finding travel?',
    description: 'Rebalance the blended signal monthly. Compare with SMIX to see whether the frequency effect also appears under a different, prespecified signal.',
    signal: '50% 12–1 + 30% 6–1 + 20% 3–1',
    schedule: 'Every month-end → next open',
    compare: 'SMIX · change frequency only',
  },
};

document.querySelectorAll('[data-arm]').forEach((button) => {
  button.addEventListener('click', () => {
    const arm = arms[button.dataset.arm];
    if (!arm) return;
    document.querySelectorAll('[data-arm]').forEach((candidate) => {
      const selected = candidate === button;
      candidate.classList.toggle('selected', selected);
      candidate.setAttribute('aria-pressed', String(selected));
    });
    document.getElementById('detail-code').textContent = button.dataset.arm;
    for (const [key, value] of Object.entries(arm)) {
      document.getElementById(`detail-${key}`).textContent = value;
    }
  });
});

const costInput = document.getElementById('cost-bps');
const tradedInput = document.getElementById('traded-multiple');
const compactNumber = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 });
const dollars = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });

function updateCosts() {
  const costBps = Number(costInput.value);
  const tradedMultiple = Number(tradedInput.value);
  const feeBps = costBps * tradedMultiple;
  const feePercent = feeBps / 100;
  document.getElementById('bps-output').textContent = `${costBps} bps`;
  document.getElementById('multiple-output').textContent = `${compactNumber.format(tradedMultiple)}× reference NAV`;
  document.getElementById('fee-percent').textContent = feePercent.toFixed(2);
  document.getElementById('fee-dollar').textContent = dollars.format(1_000_000 * feeBps / 10_000);
  document.getElementById('fee-formula').textContent = `${costBps} bps × ${compactNumber.format(tradedMultiple)} = ${compactNumber.format(feeBps)} bps = ${feePercent.toFixed(2)}%`;
  costInput.setAttribute('aria-valuetext', `${costBps} basis points per side`);
  tradedInput.setAttribute('aria-valuetext', `${tradedMultiple} times fixed reference net asset value`);
  [costInput, tradedInput].forEach((input) => {
    const fraction = (Number(input.value) - Number(input.min)) / (Number(input.max) - Number(input.min));
    input.style.setProperty('--fill', `${fraction * 100}%`);
  });
}

costInput.addEventListener('input', updateCosts);
tradedInput.addEventListener('input', updateCosts);
updateCosts();

const menuToggle = document.querySelector('.menu-toggle');
const navigation = document.getElementById('primary-nav');
function closeMenu() {
  menuToggle.setAttribute('aria-expanded', 'false');
  navigation.classList.remove('open');
}
menuToggle.addEventListener('click', () => {
  const open = menuToggle.getAttribute('aria-expanded') !== 'true';
  menuToggle.setAttribute('aria-expanded', String(open));
  navigation.classList.toggle('open', open);
});
navigation.querySelectorAll('a').forEach((link) => link.addEventListener('click', closeMenu));
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && menuToggle.getAttribute('aria-expanded') === 'true') {
    closeMenu();
    menuToggle.focus();
  }
});
