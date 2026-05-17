import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Sparkline } from "../Sparkline";

describe("Sparkline", () => {
  it("renders an svg element", () => {
    const { container } = render(<Sparkline values={[1, 2, 3]} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("uses default width=60 and height=16", () => {
    const { container } = render(<Sparkline values={[1, 2, 3]} />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("width", "60");
    expect(svg).toHaveAttribute("height", "16");
  });

  it("respects custom width and height", () => {
    const { container } = render(
      <Sparkline values={[1, 2, 3]} width={80} height={20} />,
    );
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("width", "80");
    expect(svg).toHaveAttribute("height", "20");
  });

  describe("polyline rendering", () => {
    it("renders a polyline when 2+ non-null values", () => {
      const { container } = render(<Sparkline values={[42, 43, 44]} />);
      expect(container.querySelector("polyline")).toBeInTheDocument();
    });

    it("does not render a polyline when all values are null", () => {
      const { container } = render(
        <Sparkline values={[null, null, null]} />,
      );
      expect(container.querySelector("polyline")).not.toBeInTheDocument();
    });

    it("does not render a polyline for a single non-null value", () => {
      const { container } = render(
        <Sparkline values={[42, null, null]} />,
      );
      expect(container.querySelector("polyline")).not.toBeInTheDocument();
    });

    it("does not render a polyline for an empty array", () => {
      const { container } = render(<Sparkline values={[]} />);
      expect(container.querySelector("polyline")).not.toBeInTheDocument();
    });

    it("skips null values and connects neighbors", () => {
      const { container } = render(<Sparkline values={[42, null, 44]} />);
      const polyline = container.querySelector("polyline");
      expect(polyline).toBeInTheDocument();
      // 2 points: index 0 and index 2
      const pts = polyline!.getAttribute("points")!.trim().split(" ");
      expect(pts).toHaveLength(2);
    });

    it("renders flat line when all values are equal (max===min)", () => {
      const { container } = render(<Sparkline values={[42, 42, 42]} />);
      const polyline = container.querySelector("polyline");
      expect(polyline).toBeInTheDocument();
      // All points should share the same y (height/2 = 8)
      const pts = polyline!.getAttribute("points")!.trim().split(" ");
      const ys = pts.map((p) => parseFloat(p.split(",")[1]));
      expect(ys.every((y) => y === ys[0])).toBe(true);
    });

    it("uses currentColor stroke", () => {
      const { container } = render(<Sparkline values={[1, 2, 3]} />);
      const polyline = container.querySelector("polyline");
      expect(polyline).toHaveAttribute("stroke", "currentColor");
    });

    it("uses fill=none", () => {
      const { container } = render(<Sparkline values={[1, 2, 3]} />);
      const polyline = container.querySelector("polyline");
      expect(polyline).toHaveAttribute("fill", "none");
    });
  });

  describe("refValue reference line", () => {
    it("renders a dashed line when refValue is provided with 2+ data points", () => {
      const { container } = render(
        <Sparkline values={[70, 71, 72]} refValue={68} />,
      );
      const line = container.querySelector("line");
      expect(line).toBeInTheDocument();
      expect(line).toHaveAttribute("stroke-dasharray", "2 2");
    });

    it("does not render a reference line when refValue is not provided", () => {
      const { container } = render(<Sparkline values={[70, 71, 72]} />);
      expect(container.querySelector("line")).not.toBeInTheDocument();
    });

    it("does not render a reference line when refValue is null", () => {
      const { container } = render(
        <Sparkline values={[70, 71, 72]} refValue={null} />,
      );
      expect(container.querySelector("line")).not.toBeInTheDocument();
    });

    it("does not render a reference line when fewer than 2 data points", () => {
      const { container } = render(
        <Sparkline values={[null, null]} refValue={70} />,
      );
      expect(container.querySelector("line")).not.toBeInTheDocument();
    });

    it("includes refValue in the y-scale so the line is always within viewBox bounds", () => {
      // data range 72–74, target 68 — without including refValue, the line would be clipped
      const { container } = render(
        <Sparkline values={[72, 73, 74]} refValue={68} height={16} />,
      );
      const line = container.querySelector("line");
      expect(line).toBeInTheDocument();
      const y = parseFloat(line!.getAttribute("y1")!);
      // y should be within [0, 16] (the viewBox height)
      expect(y).toBeGreaterThanOrEqual(0);
      expect(y).toBeLessThanOrEqual(16);
    });
  });
});
