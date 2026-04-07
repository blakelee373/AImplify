import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center h-full bg-background">
      <div className="text-center max-w-lg px-6">
        <div className="text-5xl mb-4">✨</div>
        <h1 className="text-4xl font-bold tracking-tight text-foreground">
          Welcome to AImplify
        </h1>
        <p className="mt-4 text-lg text-text-muted leading-relaxed">
          Tell us how your business works, and we&apos;ll handle the rest.
          No tech skills needed.
        </p>
        <Link
          href="/chat"
          className="mt-8 inline-block px-8 py-3 bg-primary text-white rounded-full font-semibold hover:bg-primary-hover transition-colors shadow-lg shadow-primary/25"
        >
          Start Chatting
        </Link>
      </div>
    </div>
  );
}
