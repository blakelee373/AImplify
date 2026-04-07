import { Suspense } from "react";
import { IntegrationsView } from "@/components/IntegrationsView";

export default function IntegrationsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-full text-text-muted">
          Loading...
        </div>
      }
    >
      <IntegrationsView />
    </Suspense>
  );
}
