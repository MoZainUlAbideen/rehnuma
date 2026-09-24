"use client";

// Any button on the site can open the chat widget, optionally with a sample bill preselected.
export const OPEN_CHAT_EVENT = "rehnuma:open-chat";

export interface OpenChatDetail {
  sampleId?: string;
  question?: string;
}

export function openChat(detail: OpenChatDetail = {}) {
  window.dispatchEvent(new CustomEvent<OpenChatDetail>(OPEN_CHAT_EVENT, { detail }));
}

export function OpenChatButton({
  className,
  children,
  sampleId,
  question,
}: {
  className?: string;
  children: React.ReactNode;
} & OpenChatDetail) {
  return (
    <button type="button" className={className} onClick={() => openChat({ sampleId, question })}>
      {children}
    </button>
  );
}
