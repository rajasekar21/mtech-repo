import { create } from "zustand";
import { get, post, uploadFile } from "@/lib/api";
import type {
  ApiSpec,
  ApiEndpoint,
  ApiDependency,
  Flow,
  SearchResponse,
  FilterParams,
  PaginatedResponse,
} from "@/types";

interface CatalogState {
  specs: ApiSpec[];
  currentSpec: ApiSpec | null;
  endpoints: ApiEndpoint[];
  dependencies: ApiDependency[];
  flows: Flow[];
  searchResults: SearchResponse | null;
  isLoading: boolean;
  isSearching: boolean;
  isUploading: boolean;
  uploadProgress: number;
  error: string | null;
  filters: FilterParams;

  fetchSpecs: (filters?: FilterParams) => Promise<void>;
  fetchSpec: (id: string) => Promise<void>;
  fetchEndpoints: (specId: string, filters?: FilterParams) => Promise<void>;
  fetchDependencies: (specId: string) => Promise<void>;
  fetchFlows: (specId: string) => Promise<void>;
  uploadSpec: (
    file: File,
    metadata: { name: string; version: string; description: string }
  ) => Promise<ApiSpec>;
  searchEndpoints: (query: string, specId?: string) => Promise<void>;
  setCurrentSpec: (spec: ApiSpec | null) => void;
  setFilters: (filters: Partial<FilterParams>) => void;
  clearSearch: () => void;
  clearError: () => void;
}

export const useCatalogStore = create<CatalogState>()((set) => ({
  specs: [],
  currentSpec: null,
  endpoints: [],
  dependencies: [],
  flows: [],
  searchResults: null,
  isLoading: false,
  isSearching: false,
  isUploading: false,
  uploadProgress: 0,
  error: null,
  filters: {},

  fetchSpecs: async (filters?: FilterParams) => {
    set({ isLoading: true, error: null });
    try {
      const params: Record<string, unknown> = {};
      if (filters?.search) params.search = filters.search;
      if (filters?.tags?.length) params.tags = filters.tags.join(",");
      if (filters?.risk_level) params.risk_level = filters.risk_level;
      if (filters?.status) params.status = filters.status;
      if (filters?.page) params.page = filters.page;
      if (filters?.page_size) params.page_size = filters.page_size;

      const response = await get<PaginatedResponse<ApiSpec>>("/api/specs", params);
      set({ specs: response.items, isLoading: false });
    } catch (err) {
      const message =
        (err as { message?: string })?.message ?? "Failed to fetch specs";
      set({ error: message, isLoading: false });
    }
  },

  fetchSpec: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      const spec = await get<ApiSpec>(`/api/specs/${id}`);
      set({ currentSpec: spec, isLoading: false });
    } catch (err) {
      const message =
        (err as { message?: string })?.message ?? "Failed to fetch spec";
      set({ error: message, isLoading: false });
    }
  },

  fetchEndpoints: async (specId: string, filters?: FilterParams) => {
    set({ isLoading: true, error: null });
    try {
      const params: Record<string, unknown> = {};
      if (filters?.search) params.search = filters.search;
      if (filters?.tags?.length) params.tags = filters.tags.join(",");
      if (filters?.risk_level) params.risk_level = filters.risk_level;
      if (filters?.auth_method) params.auth_method = filters.auth_method;
      if (filters?.deprecated !== undefined)
        params.deprecated = filters.deprecated;
      if (filters?.page) params.page = filters.page;
      if (filters?.page_size) params.page_size = filters.page_size;

      const response = await get<PaginatedResponse<ApiEndpoint>>(
        `/api/specs/${specId}/endpoints`,
        params
      );
      set({ endpoints: response.items, isLoading: false });
    } catch (err) {
      const message =
        (err as { message?: string })?.message ?? "Failed to fetch endpoints";
      set({ error: message, isLoading: false });
    }
  },

  fetchDependencies: async (specId: string) => {
    set({ isLoading: true, error: null });
    try {
      const deps = await get<ApiDependency[]>(`/api/specs/${specId}/dependencies`);
      set({ dependencies: deps, isLoading: false });
    } catch (err) {
      const message =
        (err as { message?: string })?.message ?? "Failed to fetch dependencies";
      set({ error: message, isLoading: false });
    }
  },

  fetchFlows: async (specId: string) => {
    set({ isLoading: true, error: null });
    try {
      const flows = await get<Flow[]>(`/api/specs/${specId}/flows`);
      set({ flows, isLoading: false });
    } catch (err) {
      const message =
        (err as { message?: string })?.message ?? "Failed to fetch flows";
      set({ error: message, isLoading: false });
    }
  },

  uploadSpec: async (
    file: File,
    metadata: { name: string; version: string; description: string }
  ) => {
    set({ isUploading: true, uploadProgress: 0, error: null });
    try {
      const spec = await uploadFile<ApiSpec>("/api/specs/upload", file, {
        name: metadata.name,
        version: metadata.version,
        description: metadata.description,
      });
      set((state) => ({
        specs: [spec, ...state.specs],
        isUploading: false,
        uploadProgress: 100,
      }));
      return spec;
    } catch (err) {
      const message =
        (err as { message?: string })?.message ?? "Failed to upload spec";
      set({ error: message, isUploading: false, uploadProgress: 0 });
      throw err;
    }
  },

  searchEndpoints: async (query: string, specId?: string) => {
    set({ isSearching: true, error: null });
    try {
      const params: Record<string, unknown> = { q: query };
      if (specId) params.spec_id = specId;
      const results = await post<SearchResponse>("/api/search", { query, spec_id: specId });
      set({ searchResults: results, isSearching: false });
    } catch (err) {
      const message =
        (err as { message?: string })?.message ?? "Search failed";
      set({ error: message, isSearching: false });
    }
  },

  setCurrentSpec: (spec: ApiSpec | null) => set({ currentSpec: spec }),

  setFilters: (filters: Partial<FilterParams>) =>
    set((state) => ({ filters: { ...state.filters, ...filters } })),

  clearSearch: () => set({ searchResults: null }),

  clearError: () => set({ error: null }),
}));
