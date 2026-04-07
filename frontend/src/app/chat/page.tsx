import { ChatWindow } from "@/components/ChatWindow";

export default function ChatPage() {
  return (
    <div className="flex flex-col h-full">
      <div className="border-b px-6 py-4">
        <h1 className="text-xl font-semibold">Chat</h1>
      </div>
      <ChatWindow />
    </div>
  );
}
