import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { CarouselCard, CarouselInfo } from "../../../../../apps/yongin-platform-app/src/components/CarouselCard";

describe("CarouselCard", () => {
  it("renders header title and arrows with callbacks", () => {
    const handlePrev = vi.fn();
    const handleNext = vi.fn();

    render(
      <CarouselCard>
        <CarouselCard.Header
          title="관리 카드"
          showArrows
          onPrev={handlePrev}
          onNext={handleNext}
        />
        <CarouselCard.Content>본문</CarouselCard.Content>
      </CarouselCard>
    );

    expect(screen.getByRole("heading", { name: "관리 카드" })).toBeInTheDocument();
    const prevButton = screen.getByLabelText("prev");
    const nextButton = screen.getByLabelText("next");

    fireEvent.click(prevButton);
    fireEvent.click(nextButton);

    expect(handlePrev).toHaveBeenCalledTimes(1);
    expect(handleNext).toHaveBeenCalledTimes(1);
  });

  it("hides arrows when showArrows is false", () => {
    render(
      <CarouselCard>
        <CarouselCard.Header title="보이지 않는 화살표" showArrows={false} />
      </CarouselCard>
    );

    expect(screen.queryByLabelText("prev")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("next")).not.toBeInTheDocument();
  });
});

describe("CarouselInfo", () => {
  it("renders image, tag, title, and description", () => {
    render(
      <CarouselInfo>
        <CarouselInfo.Image src="/images/sample.png" alt="관리 이미지" />
        <CarouselInfo.Tag>안전</CarouselInfo.Tag>
        <CarouselInfo.Title>현장 점검</CarouselInfo.Title>
        <CarouselInfo.Description>설비 점검 내용을 확인합니다.</CarouselInfo.Description>
      </CarouselInfo>
    );

    const image = screen.getByAltText("관리 이미지") as HTMLImageElement;
    expect(image).toBeInTheDocument();
    expect(image.src).toContain("/images/sample.png");

    expect(screen.getByText("안전")).toBeInTheDocument();

    const title = screen.getByRole("heading", { name: "현장 점검" });
    expect(title.tagName).toBe("H3");

    const description = screen.getByText("설비 점검 내용을 확인합니다.");
    expect(description.tagName).toBe("P");
  });

  it("defaults image alt text to empty string when omitted", () => {
    const { container } = render(
      <CarouselInfo>
        <CarouselInfo.Image src="/images/placeholder.png" />
      </CarouselInfo>
    );

    const image = container.querySelector("img");
    expect(image).not.toBeNull();
    expect(image).toHaveAttribute("alt", "");
  });
});
