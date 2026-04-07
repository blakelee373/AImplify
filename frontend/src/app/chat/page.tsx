import { Suspense } from "react";
import { ChatView } from "@/components/ChatView";

export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-full text-text-muted">
          Loading...
        </div>
      }
    >
      <ChatView />
    </Suspense>
  );
}
