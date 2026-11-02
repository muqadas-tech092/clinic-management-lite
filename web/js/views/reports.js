/* Placeholder until this module is ported in a later stage. */
import { freshView, pageHead, emptyState, t } from "../ui.js";
export function render(_root, app) {
  const root = freshView();
  root.innerHTML = pageHead(t("reports")) + '<div class="card">' + emptyState(t("no_data"), "", "inbox") + '</div>';
}
