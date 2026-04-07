import { ChatWindow } from "@/components/ChatWindow";

export default function ChatPage() {
  return (
    <div className="flex flex-col h-screen">
      <div className="border-b border-stone-200 px-6 py-4">
        <h1 className="text-xl font-semibold text-stone-900">Chat</h1>
        <p className="text-sm text-stone-500">
          Tell me about a task you or your staff do repeatedly
        </p>
      </div>
      <ChatWindow />
    </div>
  );
}
