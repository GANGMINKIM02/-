/**
 * PDF 추출 시 브라우저에서 이미지를 base64로 인코딩해 서버에 전달한다.
 * (Vercel 등에서 서버 측 이미지 경로 해석 실패 방지)
 */
import type { ImagePlacement, TranslationSegment } from "../api/client";
import { filterPlacementsForExport } from "./translationSections";

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

function placementImageUrl(placement: ImagePlacement): string {
  if (placement.image_url?.startsWith("http")) {
    return placement.image_url;
  }
  return `${window.location.origin}/images/${placement.image_file}`;
}

async function encodePlacementImage(
  placement: ImagePlacement,
): Promise<ImagePlacement> {
  if (placement.image_base64) return placement;
  try {
    const res = await fetch(placementImageUrl(placement));
    if (!res.ok) return placement;
    const blob = await res.blob();
    const dataUrl = await blobToDataUrl(blob);
    return { ...placement, image_base64: dataUrl };
  } catch {
    return placement;
  }
}

export async function enrichSegmentsForExport(
  segments: TranslationSegment[],
): Promise<TranslationSegment[]> {
  return Promise.all(
    segments.map(async (segment) => {
      const placements = filterPlacementsForExport(
        segment.easy_text,
        segment.image_placements ?? [],
      );
      if (!placements.length) return { ...segment, image_placements: [] };
      const encoded = await Promise.all(placements.map(encodePlacementImage));
      return { ...segment, image_placements: encoded };
    }),
  );
}
