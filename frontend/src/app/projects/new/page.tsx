"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Plus, Target, Wrench, FileCheck2 } from "lucide-react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { createAutomationProject } from "@/lib/api";
import type { AutomationOwnerType } from "@/lib/types";

export default function NewProjectPage() {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [ownerType, setOwnerType] = useState<AutomationOwnerType>("personal");
  const [currentProcess, setCurrentProcess] = useState("");
  const [workingDefinition, setWorkingDefinition] = useState("");
  const [clientContext, setClientContext] = useState("");
  const [requiredTools, setRequiredTools] = useState("");
  const [inputExamples, setInputExamples] = useState("");
  const [outputExamples, setOutputExamples] = useState("");

  async function submit() {
    if (!name.trim() || !goal.trim()) {
      toast.error("Add a project name and the outcome you want.");
      return;
    }

    setSaving(true);
    try {
      const project = await createAutomationProject({
        name,
        goal,
        owner_type: ownerType,
        current_process: currentProcess,
        working_definition: workingDefinition,
        client_context: clientContext,
        required_tools: requiredTools,
        input_examples: inputExamples,
        output_examples: outputExamples,
      });
      router.push(`/projects/${project.id}`);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Could not create project");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-4xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-[#F2EFE8]">New Automation Project</h1>
        <p className="text-[#A8A29A] text-sm mt-1">
          Capture the business problem, examples, and constraints before asking an agent to build.
        </p>
      </div>

      <div className="space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { icon: Target, title: "Outcome", copy: "What should exist when this works." },
            { icon: Wrench, title: "Context", copy: "Client data, tools, APIs, constraints." },
            { icon: FileCheck2, title: "Proof", copy: "Examples that make testing concrete." },
          ].map(({ icon: Icon, title, copy }) => (
            <div key={title} className="rounded-md border border-[#2A2A30] bg-[#141418] px-4 py-3">
              <Icon className="h-4 w-4 text-[#BCA06A] mb-2" />
              <p className="text-sm font-medium text-[#F2EFE8]">{title}</p>
              <p className="text-xs text-[#A8A29A] mt-1">{copy}</p>
            </div>
          ))}
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-[#F2EFE8]">Project name</label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Client support ticket automation"
            className="border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8] placeholder:text-[#6F6A62] focus-visible:ring-[#BCA06A]"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-[#F2EFE8]">Who is it for?</label>
          <Select value={ownerType} onValueChange={(v) => setOwnerType(v as AutomationOwnerType)}>
            <SelectTrigger className="max-w-xs border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8] focus:ring-[#BCA06A]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8]">
              <SelectItem value="personal">Personal</SelectItem>
              <SelectItem value="your_business">Your business</SelectItem>
              <SelectItem value="client">Client</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-[#F2EFE8]">Goal / desired outcome</label>
          <Textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="What should this automation achieve when it works?"
            rows={4}
            className="border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8] placeholder:text-[#6F6A62] focus-visible:ring-[#BCA06A]"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-[#F2EFE8]">
            Current process / pain <span className="text-[#A8A29A] font-normal">(optional now)</span>
          </label>
          <Textarea
            value={currentProcess}
            onChange={(e) => setCurrentProcess(e.target.value)}
            placeholder="What do you or the client do manually today?"
            rows={4}
            className="border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8] placeholder:text-[#6F6A62] focus-visible:ring-[#BCA06A]"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-[#F2EFE8]">
            Client context / memory <span className="text-[#A8A29A] font-normal">(optional)</span>
          </label>
          <Textarea
            value={clientContext}
            onChange={(e) => setClientContext(e.target.value)}
            placeholder="Who is this for? What company/client context, tone, data, or constraints should the automation respect?"
            rows={3}
            className="border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8] placeholder:text-[#6F6A62] focus-visible:ring-[#BCA06A]"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-[#F2EFE8]">
            Required tools, APIs, or data <span className="text-[#A8A29A] font-normal">(optional)</span>
          </label>
          <Textarea
            value={requiredTools}
            onChange={(e) => setRequiredTools(e.target.value)}
            placeholder="e.g. Gmail, Airtable, Slack, Exa, CRM export, local CSV, private docs..."
            rows={3}
            className="border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8] placeholder:text-[#6F6A62] focus-visible:ring-[#BCA06A]"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-[#F2EFE8]">
            What working means <span className="text-[#A8A29A] font-normal">(optional now)</span>
          </label>
          <Textarea
            value={workingDefinition}
            onChange={(e) => setWorkingDefinition(e.target.value)}
            placeholder="Give one practical proof that the automation works."
            rows={3}
            className="border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8] placeholder:text-[#6F6A62] focus-visible:ring-[#BCA06A]"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-[#F2EFE8]">Sample inputs</label>
            <Textarea
              value={inputExamples}
              onChange={(e) => setInputExamples(e.target.value)}
              placeholder="Paste one or two realistic inputs the automation should handle."
              rows={5}
              className="border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8] placeholder:text-[#6F6A62] focus-visible:ring-[#BCA06A]"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-[#F2EFE8]">Expected outputs</label>
            <Textarea
              value={outputExamples}
              onChange={(e) => setOutputExamples(e.target.value)}
              placeholder="What should a good output look like? Structure, tone, fields, decisions..."
              rows={5}
              className="border-[#2A2A30] bg-[#1B1C20] text-[#F2EFE8] placeholder:text-[#6F6A62] focus-visible:ring-[#BCA06A]"
            />
          </div>
        </div>

        <button
          onClick={submit}
          disabled={saving}
          className="inline-flex items-center rounded-md bg-[#EEE8DC] px-4 h-10 text-sm font-semibold text-[#171717] hover:bg-[#DED4C3] disabled:opacity-50 transition-colors"
        >
          {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
          Create project
        </button>
      </div>
    </div>
  );
}
