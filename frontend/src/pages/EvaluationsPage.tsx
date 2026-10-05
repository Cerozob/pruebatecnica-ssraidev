import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Flashbar, { type FlashbarProps } from "@cloudscape-design/components/flashbar";
import Header from "@cloudscape-design/components/header";
import Link from "@cloudscape-design/components/link";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import Table from "@cloudscape-design/components/table";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { useApi } from "../api/context";
import type { EvaluationSummary } from "../api/types";
import { formatDate, formatPercent, isActiveEvaluation, STATUS_LABELS, statusType } from "../utils/format";

const REFRESH_MS = 10000;

export default function EvaluationsPage() {
  const api = useApi();
  const navigate = useNavigate();
  const [evaluations, setEvaluations] = useState<EvaluationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [flash, setFlash] = useState<FlashbarProps.MessageDefinition[]>([]);

  const load = useCallback(async () => {
    try {
      setEvaluations((await api.listEvaluations()).evaluations);
    } catch (error) {
      setFlash([{ type: "error", content: (error as Error).message, id: "load" }]);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    let cancelled = false;
    api.listEvaluations()
      .then(({ evaluations: items }) => !cancelled && setEvaluations(items))
      .catch((error: Error) => !cancelled && setFlash([{ type: "error", content: error.message, id: "load" }]))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [api]);

  // Mientras haya evaluaciones en curso, la lista se actualiza sola.
  const active = evaluations.some((evaluation) => isActiveEvaluation(evaluation.status));
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(timer);
  }, [active, load]);

  // Una evaluación a la vez; la API también lo exige (409).
  const inProgress = evaluations.some((item) => item.status === "PENDING" || item.status === "RUNNING");

  const start = async () => {
    setStarting(true);
    try {
      const evaluation = await api.startEvaluation();
      setFlash([
        {
          type: "success",
          content: "Evaluación iniciada. Puede tardar varios minutos.",
          id: "started",
          dismissible: true,
          onDismiss: () => setFlash([]),
        },
      ]);
      setEvaluations((current) => [evaluation, ...current]);
    } catch (error) {
      setFlash([{ type: "error", content: (error as Error).message, id: "start" }]);
    } finally {
      setStarting(false);
    }
  };

  return (
    <SpaceBetween size="m">
      <Flashbar items={flash} />
      <Table
        loading={loading}
        loadingText="Cargando evaluaciones"
        items={evaluations}
        trackBy="evaluationId"
        variant="full-page"
        header={
          <Header
            variant="awsui-h1-sticky"
            description="Precisión, groundedness, información insuficiente y prompt injection, calificados por un modelo juez."
            actions={
              <SpaceBetween size="xs" direction="horizontal">
                <Button iconName="refresh" ariaLabel="Actualizar" onClick={() => void load()} />
                <Button
                  variant="primary"
                  onClick={() => void start()}
                  loading={starting}
                  disabled={inProgress}
                  disabledReason="Ya hay una evaluación en curso."
                >
                  Iniciar evaluación
                </Button>
              </SpaceBetween>
            }
          >
            Evaluaciones
          </Header>
        }
        empty={<Box textAlign="center">Aún no hay evaluaciones.</Box>}
        columnDefinitions={[
          {
            id: "createdAt",
            header: "Fecha",
            cell: (item) => (
              <Link
                href={`/evaluaciones/${item.evaluationId}`}
                onFollow={(event) => {
                  event.preventDefault();
                  navigate(`/evaluaciones/${item.evaluationId}`);
                }}
              >
                {formatDate(item.createdAt)}
              </Link>
            ),
          },
          {
            id: "status",
            header: "Estado",
            cell: (item) => <StatusIndicator type={statusType(item.status)}>{STATUS_LABELS[item.status]}</StatusIndicator>,
          },
          {
            id: "progress",
            header: "Progreso",
            cell: (item) => (item.progress ? `${item.progress.completed} / ${item.progress.total}` : "-"),
          },
          { id: "passed", header: "Aprobadas", cell: (item) => (item.summary ? `${item.summary.passed} / ${item.summary.total}` : "-") },
          { id: "accuracy", header: "Precisión", cell: (item) => formatPercent(item.summary?.accuracy) },
          { id: "groundedness", header: "Groundedness", cell: (item) => formatPercent(item.summary?.groundedness) },
          {
            id: "insufficient",
            header: "Info. insuficiente",
            cell: (item) => formatPercent(item.summary?.insufficientInformation),
          },
          {
            id: "injection",
            header: "Injection bloqueado",
            cell: (item) => formatPercent(item.summary?.promptInjectionBlocked),
          },
        ]}
      />
    </SpaceBetween>
  );
}
