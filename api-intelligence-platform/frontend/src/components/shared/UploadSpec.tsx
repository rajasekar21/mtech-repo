"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { toast } from "sonner";
import { useCatalogStore } from "@/store/catalog";

interface UploadSpecProps {
  onClose: () => void;
}

export default function UploadSpec({ onClose }: UploadSpecProps) {
  const { uploadSpec, isUploading } = useCatalogStore();
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [version, setVersion] = useState("");
  const [description, setDescription] = useState("");

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file || !name || !version) {
      toast.error("Name, version, and file are required.");
      return;
    }

    try {
      await uploadSpec(file, { name, version, description });
      toast.success("Specification uploaded.");
      onClose();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Upload failed."
      );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-100">Upload Spec</h2>
            <p className="text-sm text-slate-500">
              Add an OpenAPI, Swagger, XML, or PDF specification.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-800 hover:text-slate-300"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Specification name"
            className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200"
          />
          <input
            value={version}
            onChange={(event) => setVersion(event.target.value)}
            placeholder="Version"
            className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200"
          />
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Description"
            rows={4}
            className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200"
          />
          <input
            type="file"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="block w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-300 file:mr-3 file:rounded-md file:border-0 file:bg-indigo-600 file:px-3 file:py-1.5 file:text-white"
          />

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isUploading}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {isUploading ? "Uploading..." : "Upload"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
