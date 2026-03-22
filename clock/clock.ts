function formatTime(d: Date): string {
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

function formatDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const w = ["日", "月", "火", "水", "木", "金", "土"][d.getDay()];
  return `${y}/${m}/${day}（${w}）`;
}

function tick(): void {
  const now = new Date();

  const clock = document.getElementById("clock");
  if (clock) {
    const hh = String(now.getHours()).padStart(2, "0");
    const mm = String(now.getMinutes()).padStart(2, "0");
    const ss = String(now.getSeconds()).padStart(2, "0");
    clock.innerHTML = `${hh}:${mm}:<span class="sec">${ss}</span>`;
    clock.classList.remove("pulse");
    // 直後に付けるとアニメが走らないことがあるので、1フレーム遅らせる
    requestAnimationFrame(() => clock.classList.add("pulse"));
  }

  const dateEl = document.getElementById("date");
  if (dateEl) {
    dateEl.textContent = formatDate(now);
  }
}

tick();
setInterval(tick, 1000);

