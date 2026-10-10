import type { Cluster } from "./types";
import { getLanguage, translate } from "../i18n";
import { formatCount } from "./utils";

/** Localize generated presentation labels without renaming stored groups or source names. */
export function clusterDisplayTitle(cluster: Cluster): string {
  if (getLanguage() === "ru" && cluster.directory) {
    if (!cluster.current_snapshot)
      return translate("Group awaiting a saved graph");
    const count = new Set(cluster.current_snapshot.member_ids).size;
    return translate(
      count === 1
        ? "{reason} · {count} company"
        : "{reason} · {count} companies",
      {
        reason: translate(
          cluster.directory.primary_reason?.label ?? "Relationship group",
        ),
        count: formatCount(count),
      },
    );
  }
  return (
    cluster.directory?.title ||
    cluster.name ||
    translate("Saved relationship group")
  );
}
