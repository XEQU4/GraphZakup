"""Legacy import compatibility. Reading this helper never invokes a provider."""
from .services import saved_analysis
from .explainer import explain_cluster as graph_template


def explain_cluster(cluster):
    _, explanation, _ = saved_analysis(cluster, cluster.current_snapshot)
    return explanation.text if explanation else graph_template(cluster)
