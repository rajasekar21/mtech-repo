import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Notification } from "@/types";

interface UIState {
  theme: "dark" | "light" | "system";
  sidebarCollapsed: boolean;
  activeSpecId: string | null;
  notifications: Notification[];
  unreadCount: number;

  setTheme: (theme: "dark" | "light" | "system") => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setActiveSpecId: (id: string | null) => void;
  addNotification: (notification: Omit<Notification, "id" | "read" | "created_at">) => void;
  markNotificationRead: (id: string) => void;
  markAllNotificationsRead: () => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;
}

function generateId(): string {
  return Math.random().toString(36).substring(2, 9);
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      theme: "dark",
      sidebarCollapsed: false,
      activeSpecId: null,
      notifications: [],
      unreadCount: 0,

      setTheme: (theme) => set({ theme }),

      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

      setActiveSpecId: (id) => set({ activeSpecId: id }),

      addNotification: (notification) => {
        const newNotification: Notification = {
          ...notification,
          id: generateId(),
          read: false,
          created_at: new Date().toISOString(),
        };
        set((state) => ({
          notifications: [newNotification, ...state.notifications].slice(0, 50),
          unreadCount: state.unreadCount + 1,
        }));
      },

      markNotificationRead: (id) =>
        set((state) => ({
          notifications: state.notifications.map((n) =>
            n.id === id ? { ...n, read: true } : n
          ),
          unreadCount: Math.max(
            0,
            state.notifications.filter((n) => !n.read && n.id !== id).length
          ),
        })),

      markAllNotificationsRead: () =>
        set((state) => ({
          notifications: state.notifications.map((n) => ({ ...n, read: true })),
          unreadCount: 0,
        })),

      removeNotification: (id) =>
        set((state) => {
          const notification = state.notifications.find((n) => n.id === id);
          return {
            notifications: state.notifications.filter((n) => n.id !== id),
            unreadCount: notification?.read
              ? state.unreadCount
              : Math.max(0, state.unreadCount - 1),
          };
        }),

      clearNotifications: () => set({ notifications: [], unreadCount: 0 }),
    }),
    {
      name: "ui-storage",
      partialize: (state) => ({
        theme: state.theme,
        sidebarCollapsed: state.sidebarCollapsed,
        activeSpecId: state.activeSpecId,
      }),
    }
  )
);
