import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import ContentLayout from "@cloudscape-design/components/content-layout";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Select, { type SelectProps } from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import { useEffect, useState } from "react";
import { useApi } from "../api/context";

const HOURS: SelectProps.Option[] = [
  { label: "Última hora", value: "1" },
  { label: "Últimas 24 horas", value: "24" },
  { label: "Últimos 7 días", value: "168" },
];
const EVENT_LIMIT = 500;

/** Visor básico de CloudWatch: solo los log groups con las etiquetas de la aplicación (ADR-037). */
export default function LogsPage() {
  const api = useApi();
  const [groups, setGroups] = useState<SelectProps.Option[]>([]);
  const [group, setGroup] = useState<SelectProps.Option | null>(null);
  const [hours, setHours] = useState<SelectProps.Option>(HOURS[1]);
  const [text, setText] = useState("");
  const [loadingGroups, setLoadingGroups] = useState(true);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listLogGroups()
      .then(({ logGroups }) => setGroups(logGroups.map((logGroup) => ({ label: logGroup.name, value: logGroup.id }))))
      .catch((loadError: Error) => setError(loadError.message))
      .finally(() => setLoadingGroups(false));
  }, [api]);

  const loadEvents = async (selected = group, range = hours) => {
    if (!selected?.value) return;
    setLoadingEvents(true);
    setError(null);
    try {
      setText(await api.getLogEvents(selected.value, Number(range.value), EVENT_LIMIT));
    } catch (loadError) {
      setError((loadError as Error).message);
    } finally {
      setLoadingEvents(false);
    }
  };

  return (
    <ContentLayout header={<Header variant="h1">Logs</Header>}>
      <Container
        header={
          <Header
            variant="h2"
            actions={
              <Button
                iconName="refresh"
                onClick={() => void loadEvents()}
                loading={loadingEvents}
                disabled={!group}
              >
                Actualizar
              </Button>
            }
          >
            Eventos de CloudWatch
          </Header>
        }
      >
        <SpaceBetween size="m">
          <SpaceBetween size="m" direction="horizontal">
            <FormField label="Log group">
              <Select
                selectedOption={group}
                options={groups}
                statusType={loadingGroups ? "loading" : "finished"}
                loadingText="Cargando log groups"
                placeholder="Elige un log group"
                filteringType="auto"
                empty="No hay log groups con las etiquetas de la aplicación"
                onChange={({ detail }) => {
                  setGroup(detail.selectedOption);
                  void loadEvents(detail.selectedOption, hours);
                }}
              />
            </FormField>
            <FormField label="Periodo">
              <Select
                selectedOption={hours}
                options={HOURS}
                onChange={({ detail }) => {
                  setHours(detail.selectedOption);
                  void loadEvents(group, detail.selectedOption);
                }}
              />
            </FormField>
          </SpaceBetween>
          {error && <StatusIndicator type="error">{error}</StatusIndicator>}
          <Box variant="code">
            <pre style={{ maxHeight: "60vh", overflow: "auto", margin: 0, whiteSpace: "pre-wrap" }}>
              {text || (group ? "Sin eventos en el periodo." : "Elige un log group para ver sus eventos.")}
            </pre>
          </Box>
        </SpaceBetween>
      </Container>
    </ContentLayout>
  );
}
