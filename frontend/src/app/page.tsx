import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-6">
      <div className="max-w-md text-center space-y-6">
        <h1 className="text-4xl font-bold tracking-tight text-stone-900">
          Welcome to <span className="text-primary">AImplify</span>
        </h1>
        <p className="text-lg text-stone-600">
          Describe how your business works, and we&apos;ll build AI agents to
          handle your repetitive tasks.
        </p>
        <Link
          href="/chat"
          className="inline-flex items-center justify-center px-6 py-3 rounded-lg bg-primary text-white font-semibold hover:bg-primary-hover transition-colors"
        >
          Start a Conversation
        </Link>
      </div>
    </div>
  );
}
