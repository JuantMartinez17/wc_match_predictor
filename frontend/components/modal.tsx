"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";

interface Props {
  open: boolean;
  onClose: () => void;
  /** Encabezado fijo del modal (queda sticky arriba). */
  header?: ReactNode;
  children: ReactNode;
  labelledBy?: string;
}

/**
 * Modal accesible sobre el elemento nativo <dialog>:
 * focus-trap, Escape y top-layer los maneja el navegador (showModal()).
 * Sumamos cierre por click en el backdrop y scroll-lock del body.
 */
export default function Modal({
  open,
  onClose,
  header,
  children,
  labelledBy,
}: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  // Sincroniza el estado de React con el método imperativo del <dialog>.
  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (open && !dlg.open) dlg.showModal();
    else if (!open && dlg.open) dlg.close();
  }, [open]);

  // Scroll-lock del fondo mientras el modal está abierto.
  // Compensa el ancho del scrollbar con padding-right para evitar el salto
  // horizontal del contenido cuando la barra desaparece.
  useEffect(() => {
    if (!open) return;
    const scrollbar = window.innerWidth - document.documentElement.clientWidth;
    const prevOverflow = document.body.style.overflow;
    const prevPadding = document.body.style.paddingRight;
    document.body.style.overflow = "hidden";
    if (scrollbar > 0) document.body.style.paddingRight = `${scrollbar}px`;
    return () => {
      document.body.style.overflow = prevOverflow;
      document.body.style.paddingRight = prevPadding;
    };
  }, [open]);

  // Escape dispara 'cancel'; el botón de cierre dispara close() → 'close'.
  // En ambos casos avisamos al padre para sincronizar el estado.
  function handleClose() {
    onClose();
  }

  // Click en el backdrop = click cuyo target es el propio <dialog> (no su contenido).
  function handleClick(e: React.MouseEvent<HTMLDialogElement>) {
    if (e.target === ref.current) onClose();
  }

  return (
    <dialog
      ref={ref}
      onCancel={handleClose}
      onClose={handleClose}
      onClick={handleClick}
      aria-labelledby={labelledBy}
      className="m-auto w-[min(92vw,42rem)] max-h-[90vh] overflow-hidden rounded-2xl border border-[#E8E6E1] bg-white p-0 shadow-xl backdrop:cursor-pointer"
    >
      {/* Encabezado sticky con botón de cierre */}
      <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-[#E8E6E1] bg-white/95 px-6 py-4 backdrop-blur-sm">
        <div className="min-w-0">{header}</div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Cerrar"
          className="shrink-0 rounded-full p-1.5 text-[#6B6B6B] transition-colors hover:bg-[#F8F7F5] hover:text-[#1B1B1B] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#183A70] focus-visible:ring-offset-2"
        >
          <X size={18} />
        </button>
      </div>

      {/* Cuerpo scrolleable */}
      <div className="max-h-[calc(90vh-4rem)] overflow-y-auto p-6">{children}</div>
    </dialog>
  );
}
