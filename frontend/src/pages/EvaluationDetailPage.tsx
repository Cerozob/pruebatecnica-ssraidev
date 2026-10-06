import Box from "@cloudscape-design/components/box";
import BreadcrumbGroup from "@cloudscape-design/components/breadcrumb-group";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import ContentLayout from "@cloudscape-design/components/content-layout";
import ExpandableSection from "@cloudscape-design/components/expandable-section";
import Header from "@cloudscape-design/components/header";
import KeyValuePairs from "@cloudscape-design/components/key-value-pairs";
import ProgressBar from "@cloudscape-design/components/progress-bar";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import Table from "@cloudscape-design/components/table";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { useApi } from "../api/context";
import type { Evaluation, EvaluationResult } from "../api/types";
import {
  agentLabel,
  CATEGORY_LABELS,
  formatDate,
  formatPercent,
  isActiveEvaluation,
  STATUS_LABELS,
  statusType,
} from "../utils/format";

const REFRESH_MS = 8000;

// The detail endpoint already returns the whole run, so the export is built client-side.
function downloadEvaluation(evaluation: Evaluation) {
  const blob = new Blob([JSON.stringify(evaluation, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `evaluacion-${evaluation.evaluationId}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

function ResultDetail({ result }: { result: EvaluationResult }) {
  return (
    <ExpandableSection headerText="Ver detalle">
      <SpaceBetween size="s">
        <Box>
          <Box variant="awsui-key-label">Respuesta esperada o criterio</Box>
          {result.expected}
        </Box>
        <Box>
          <Box variant="awsui-key-label">Respuesta obtenida</Box>
          <div style={{ whiteSpace: "pre-wrap" }}>{result.answer || "-"}</div>
        </Box>
        <Box>
          <Box variant="awsui-key-label">Observación del juez</Box>
          {result.reason || "-"}
        </Box>
        {result.groundedness && (
          <Box>
            <Box variant="awsui-key-label">Groundedness (AgentCore Evaluations)</Box>
            {result.groundedness.reason || "-"}
          </Box>
        )}
      </SpaceBetween>
    </ExpandableSection>
  );
}

export default function EvaluationDetailPage() {
  const api = useApi();
  const navigate = useNavigate();
  const { evaluationId = "" } = useParams();
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setEvaluation(await api.getEvaluation(evaluationId));
    } catch (loadError) {
      setError((loadError as Error).message);
    }
  }, [api, evaluationId]);

  useEffect(() => {
    let cancelled = false;
    api
      .getEvaluation(evaluationId)
      .then((item) => !cancelled && setEvaluation(item))
      .catch((loadError: Error) => !cancelled && setError(loadError.message));
    return () => {
      cancelled = true;
    };
  }, [api, evaluationId]);

  const active = evaluation ? isActiveEvaluation(evaluation.status) : false;
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(timer);
  }, [active, load]);

  const progress = evaluation?.progress;
  return (
    <ContentLayout
      breadcrumbs={
        <BreadcrumbGroup
          items={[
            { text: "Evaluaciones", href: "/evaluaciones" },
            { text: evaluationId, href: `/evaluaciones/${evaluationId}` },
          ]}
          onFollow={(event) => {
            event.preventDefault();
            navigate(event.detail.href);
          }}
        />
      }
      header={
        <Header
          variant="h1"
          actions={
            <Button
              iconName="download"
              disabled={!evaluation}
              onClick={() => evaluation && downloadEvaluation(evaluation)}
            >
              Exportar JSON
            </Button>
          }
        >
          Resultados de la evaluación
        </Header>
      }
    >
      <SpaceBetween size="l">
        {error && <StatusIndicator type="error">{error}</StatusIndicator>}
        {evaluation && (
          <Container header={<Header variant="h2">Resumen</Header>}>
            <SpaceBetween size="m">
              <KeyValuePairs
                columns={4}
                items={[
                  {
                    label: "Estado",
                    value: (
                      <StatusIndicator type={statusType(evaluation.status)}>
                        {STATUS_LABELS[evaluation.status]}
                      </StatusIndicator>
                    ),
                  },
                  { label: "Iniciada", value: formatDate(evaluation.startedAt ?? evaluation.createdAt) },
                  { label: "Finalizada", value: formatDate(evaluation.finishedAt) },
                  {
                    label: "Casos aprobados",
                    value: evaluation.summary ? `${evaluation.summary.passed} / ${evaluation.summary.total}` : "-",
                  },
                  { label: "Precisión", value: formatPercent(evaluation.summary?.accuracy) },
                  { label: "Groundedness", value: formatPercent(evaluation.summary?.groundedness) },
                  {
                    label: "Información insuficiente",
                    value: formatPercent(evaluation.summary?.insufficientInformation),
                  },
                  {
                    label: "Prompt injection bloqueado",
                    value: formatPercent(evaluation.summary?.promptInjectionBlocked),
                  },
                ]}
              />
              {active && progress && (
                <ProgressBar
                  value={progress.total ? (progress.completed / progress.total) * 100 : 0}
                  label="Progreso"
                  additionalInfo={`${progress.completed} de ${progress.total} casos`}
                />
              )}
              {evaluation.error && <StatusIndicator type="error">{evaluation.error}</StatusIndicator>}
            </SpaceBetween>
          </Container>
        )}
        <Table
          loading={!evaluation && !error}
          loadingText="Cargando resultados"
          items={evaluation?.results ?? []}
          trackBy="caseId"
          wrapLines
          header={<Header variant="h2">Casos de prueba</Header>}
          empty={<Box textAlign="center">Todavía no hay resultados.</Box>}
          columnDefinitions={[
            { id: "caseId", header: "#", cell: (item) => item.caseId },
            { id: "category", header: "Tipo", cell: (item) => CATEGORY_LABELS[item.category] ?? item.category },
            { id: "question", header: "Pregunta", cell: (item) => item.question },
            {
              id: "agents",
              header: "Agentes",
              cell: (item) => (item.agents.length ? item.agents.map(agentLabel).join(" → ") : "-"),
            },
            { id: "score", header: "Puntaje", cell: (item) => item.score.toFixed(2) },
            {
              id: "groundedness",
              header: "Groundedness",
              cell: (item) => (item.groundedness ? (item.groundedness.score?.toFixed(2) ?? "Error") : "-"),
            },
            {
              id: "passed",
              header: "Resultado",
              cell: (item) => (
                <StatusIndicator type={item.passed ? "success" : "error"}>
                  {item.passed ? "Aprobado" : "No aprobado"}
                </StatusIndicator>
              ),
            },
            { id: "detail", header: "Detalle", cell: (item) => <ResultDetail result={item} /> },
          ]}
        />
      </SpaceBetween>
    </ContentLayout>
  );
}
