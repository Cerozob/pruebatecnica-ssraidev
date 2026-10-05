import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MarkdownContent } from "./MarkdownContent";

describe("MarkdownContent", () => {
  it("muestra listas, negritas y tablas de GFM", () => {
    const { container } = render(
      <MarkdownContent>{"**Opción A**\n\n- uno\n- dos\n\n| Servicio | Uso |\n| --- | --- |\n| Aurora | SQL |"}</MarkdownContent>,
    );
    expect(screen.getByText("Opción A").tagName).toBe("STRONG");
    expect(container.querySelectorAll("li")).toHaveLength(2);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Aurora" })).toBeInTheDocument();
  });

  it("muestra los enlaces como enlaces externos", () => {
    render(<MarkdownContent>{"[Docs](https://docs.aws.amazon.com/)"}</MarkdownContent>);
    expect(screen.getByRole("link", { name: /Docs/ })).toHaveAttribute("href", "https://docs.aws.amazon.com/");
  });

  it("no interpreta el HTML del modelo", () => {
    const { container } = render(<MarkdownContent>{'<img src="x" onerror="alert(1)">'}</MarkdownContent>);
    expect(container.querySelector("img")).toBeNull();
  });
});
