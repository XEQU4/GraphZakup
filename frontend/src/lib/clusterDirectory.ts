import type { Cluster } from "./types";

/** Presentation labels never rename the persisted group or its history. */
export function clusterDisplayTitle(cluster: Cluster): string {
  return cluster.directory?.title || cluster.name || "Saved relationship group";
}
