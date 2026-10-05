import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import ContentLayout from "@cloudscape-design/components/content-layout";
import FileUpload from "@cloudscape-design/components/file-upload";
import Flashbar, { type FlashbarProps } from "@cloudscape-design/components/flashbar";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { useState } from "react";
import { uploadToS3 } from "../api/client";
import { useApi } from "../api/context";

// Formatos y tamaño máximo que admite la base de conocimiento; el backend vuelve a validarlos.
const ACCEPTED = ".pdf,.txt,.md,.html,.htm,.csv,.doc,.docx,.xls,.xlsx";
const MAX_SIZE_BYTES = 50 * 1024 * 1024;

export default function DocumentsPage() {
  const api = useApi();
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [flash, setFlash] = useState<FlashbarProps.MessageDefinition[]>([]);

  const notify = (type: FlashbarProps.Type, content: string) => {
    const id = `${Date.now()}-${Math.random()}`;
    setFlash((current) => [
      { id, type, content, dismissible: true, onDismiss: () => setFlash((items) => items.filter((i) => i.id !== id)) },
      ...current,
    ]);
  };

  const tooLarge = files.filter((file) => file.size > MAX_SIZE_BYTES);

  const upload = async () => {
    setUploading(true);
    for (const file of files) {
      try {
        const target = await api.createUploadUrl(file);
        await uploadToS3(target, file);
        notify("success", `${file.name} se subió. La base de conocimiento se sincroniza automáticamente.`);
      } catch (error) {
        notify("error", `${file.name}: ${(error as Error).message}`);
      }
    }
    setFiles([]);
    setUploading(false);
  };

  const sync = async () => {
    setSyncing(true);
    try {
      const result = await api.syncKnowledgeBase();
      notify(result.started ? "success" : "info", result.message);
    } catch (error) {
      notify("error", `No se pudo sincronizar: ${(error as Error).message}`);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <ContentLayout
      header={
        <Header variant="h1" description="Los documentos se suben directo a S3 y se ingieren en la base de conocimiento.">
          Documentos
        </Header>
      }
    >
      <SpaceBetween size="l">
        <Flashbar items={flash} stackItems />
        <Container header={<Header variant="h2">Subir documentos</Header>}>
          <SpaceBetween size="m">
            <FormField
              label="Archivos"
              description="PDF, Word, Excel, CSV, HTML, Markdown o texto, de hasta 50 MB cada uno."
              errorText={tooLarge.length > 0 ? `Superan 50 MB: ${tooLarge.map((f) => f.name).join(", ")}` : undefined}
            >
              <FileUpload
                multiple
                value={files}
                onChange={({ detail }) => setFiles(detail.value)}
                accept={ACCEPTED}
                showFileSize
                showFileLastModified
                i18nStrings={{
                  uploadButtonText: (multiple) => (multiple ? "Elegir archivos" : "Elegir archivo"),
                  dropzoneText: (multiple) => (multiple ? "Suelta los archivos aquí" : "Suelta el archivo aquí"),
                  removeFileAriaLabel: (index) => `Quitar el archivo ${index + 1}`,
                  limitShowFewer: "Mostrar menos",
                  limitShowMore: "Mostrar más",
                  errorIconAriaLabel: "Error",
                }}
              />
            </FormField>
            <Button
              variant="primary"
              onClick={() => void upload()}
              loading={uploading}
              disabled={files.length === 0 || tooLarge.length > 0}
            >
              Subir
            </Button>
          </SpaceBetween>
        </Container>
        <Container
          header={
            <Header
              variant="h2"
              description="Úsala si una sincronización automática falló o se omitió porque había otra en curso."
            >
              Sincronización manual
            </Header>
          }
        >
          <SpaceBetween size="s">
            <Box>Lanza una sincronización incremental de la base de conocimiento con el bucket de documentos.</Box>
            <Button onClick={() => void sync()} loading={syncing} iconName="refresh">
              Sincronizar base de conocimiento
            </Button>
          </SpaceBetween>
        </Container>
      </SpaceBetween>
    </ContentLayout>
  );
}
