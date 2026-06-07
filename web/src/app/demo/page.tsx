import { DemoFlowPanel } from "@/demo/demo-flow-panel";

export default function DemoPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Demo Flow</h1>
      </div>
      <DemoFlowPanel />
    </div>
  );
}
