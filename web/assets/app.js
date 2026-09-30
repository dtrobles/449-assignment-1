const taskList = document.querySelector("#task-list");
const form = document.querySelector("#task-form");
let showCompleted = false;

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(payload.error || "Something went wrong.");
  return payload;
}

function formatMeta(task) {
  const due = task.due_date ? `Due ${new Date(`${task.due_date}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}` : "No due date";
  return `${task.priority[0].toUpperCase() + task.priority.slice(1)} · ${task.category} · ${due}`;
}

function renderTasks(tasks) {
  taskList.replaceChildren();
  const visible = showCompleted ? tasks : tasks.filter((task) => !task.completed);
  document.querySelector("#task-count").textContent = `${visible.length} task${visible.length === 1 ? "" : "s"} ${showCompleted ? "shown" : "remaining"}`;
  if (!visible.length) {
    taskList.innerHTML = '<li class="empty">Nothing here. Capture your next useful action.</li>';
    return;
  }
  const template = document.querySelector("#task-template");
  visible.forEach((task) => {
    const node = template.content.cloneNode(true);
    const item = node.querySelector(".task");
    const checkbox = node.querySelector(".toggle");
    item.classList.toggle("completed", task.completed);
    checkbox.checked = task.completed;
    node.querySelector("strong").textContent = task.title;
    node.querySelector("span").textContent = formatMeta(task);
    checkbox.addEventListener("change", async () => {
      await api(`/tasks/${task.id}`, { method: "PATCH", body: JSON.stringify({ completed: checkbox.checked }) });
      refresh();
    });
    node.querySelector(".delete").addEventListener("click", async () => {
      await api(`/tasks/${task.id}`, { method: "DELETE" });
      refresh();
    });
    taskList.append(node);
  });
}

async function refresh() {
  try {
    const [tasks, summary] = await Promise.all([api("/tasks"), api("/summary")]);
    renderTasks(tasks);
    [["total", summary.total], ["today", summary.today], ["overdue", summary.overdue], ["done", summary.completed]]
      .forEach(([id, value]) => { document.getElementById(id).textContent = value; });
  } catch (error) {
    taskList.innerHTML = `<li class="empty">${error.message}</li>`;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = document.querySelector("#form-message");
  const data = Object.fromEntries(new FormData(form));
  try {
    await api("/tasks", { method: "POST", body: JSON.stringify(data) });
    form.reset();
    form.category.value = "Personal";
    message.textContent = "Task added to your plan.";
    message.className = "message success";
    refresh();
  } catch (error) {
    message.textContent = error.message;
    message.className = "message";
  }
});
document.querySelector("#show-completed").addEventListener("click", (event) => {
  showCompleted = !showCompleted;
  event.currentTarget.textContent = showCompleted ? "Hide completed" : "Show completed";
  refresh();
});
refresh();
