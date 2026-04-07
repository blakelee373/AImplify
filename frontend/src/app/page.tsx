import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <h1 className="text-4xl font-bold tracking-tight">
        Welcome to AImplify
      </h1>
      <p className="mt-4 text-lg text-gray-500">
        AI operations layer for small businesses
      </p>
      <Link
        href="/chat"
        className="mt-8 px-6 py-3 bg-primary text-white rounded-lg font-medium hover:bg-primary-hover transition-colors"
      >
        Start Chatting
      </Link>
    </div>
  );
}
