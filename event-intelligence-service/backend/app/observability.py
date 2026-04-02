import base64
import logging
import os

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

logger = logging.getLogger(__name__)


def _setup() -> None:
    readers = [PrometheusMetricReader()]

    otlp_endpoint = os.getenv("GRAFANA_OTLP_ENDPOINT")
    instance_id = os.getenv("GRAFANA_INSTANCE_ID")
    api_token = os.getenv("GRAFANA_API_TOKEN")

    if otlp_endpoint and instance_id and api_token:
        creds = base64.b64encode(f"{instance_id}:{api_token}".encode()).decode()
        exporter = OTLPMetricExporter(
            endpoint=f"{otlp_endpoint}/v1/metrics",
            headers={"Authorization": f"Basic {creds}"},
        )
        readers.append(PeriodicExportingMetricReader(exporter, export_interval_millis=30_000))
        logger.info("grafana_cloud_push_enabled", extra={"endpoint": otlp_endpoint})
    else:
        logger.info("grafana_cloud_push_disabled")

    metrics.set_meter_provider(MeterProvider(metric_readers=readers))


_setup()
meter = metrics.get_meter("event_intelligence")
