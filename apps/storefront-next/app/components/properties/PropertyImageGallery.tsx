"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

import {
  Carousel,
  type CarouselApi,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/components/ui/carousel";
import { cn } from "@/lib/utils";

interface PropertyImageGalleryProps {
  images: string[];
  title: string;
}

export function PropertyImageGallery({ images, title }: PropertyImageGalleryProps) {
  const [api, setApi] = useState<CarouselApi>();
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    if (!api) return;

    const onSelect = () => setActiveIndex(api.selectedScrollSnap());
    onSelect();
    api.on("select", onSelect);
    api.on("reInit", onSelect);

    return () => {
      api.off("select", onSelect);
      api.off("reInit", onSelect);
    };
  }, [api]);

  if (images.length === 0) {
    return (
      <div className="flex aspect-[16/10] w-full items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-100 text-sm text-slate-500">
        Sin fotos — abre el detalle con sincronización RE/MAX para cargar la galería.
      </div>
    );
  }

  return (
    <div className="space-y-3" data-slot="property-gallery">
      <Carousel className="w-full" setApi={setApi} opts={{ loop: true }}>
        <CarouselContent className="ml-0">
          {images.map((src, index) => (
            <CarouselItem key={`${src}-${index}`} className="pl-0">
              <div className="relative aspect-[16/10] w-full overflow-hidden rounded-xl border border-slate-200 bg-slate-100">
                <Image
                  src={src}
                  alt={`${title} — foto ${index + 1} de ${images.length}`}
                  fill
                  className="object-cover"
                  sizes="(max-width: 1024px) 100vw, 896px"
                  priority={index === 0}
                  unoptimized
                />
              </div>
            </CarouselItem>
          ))}
        </CarouselContent>
        {images.length > 1 ? (
          <>
            <CarouselPrevious />
            <CarouselNext />
          </>
        ) : null}
      </Carousel>

      {images.length > 1 ? (
        <div className="grid grid-cols-4 gap-2 sm:grid-cols-6 md:grid-cols-8">
          {images.map((src, index) => (
            <button
              key={`thumb-${src}-${index}`}
              type="button"
              onClick={() => api?.scrollTo(index)}
              className={cn(
                "relative aspect-square overflow-hidden rounded-md border-2 transition",
                index === activeIndex
                  ? "border-slate-900 ring-2 ring-slate-900/20"
                  : "border-transparent opacity-75 hover:opacity-100"
              )}
              aria-label={`Ver foto ${index + 1}`}
              aria-current={index === activeIndex}
            >
              <Image
                src={src}
                alt=""
                fill
                className="object-cover"
                sizes="96px"
                unoptimized
              />
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}