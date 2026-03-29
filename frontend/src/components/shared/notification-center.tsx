"use client";

import { useEffect, useState } from "react";
import { BellIcon, CheckCheckIcon } from "lucide-react";
import type {
  NotificationDeliveryItem,
  NotificationItem,
  NotificationPreferences,
  PushConfiguration,
  PushSubscriptionPayload,
} from "@/types";
import { apiClient } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuthStore } from "@/stores/auth.store";

const PREFERENCE_ROWS = [
  {
    key: "inAppEnabled",
    label: "In-app notifications",
    description: "Show updates in your FundaConnect inbox.",
  },
  {
    key: "emailEnabled",
    label: "Email notifications",
    description: "Send lesson, payout, refund, and verification updates by email.",
  },
  {
    key: "smsEnabled",
    label: "SMS notifications",
    description: "Send important updates to the phone number saved on your account.",
  },
  {
    key: "pushEnabled",
    label: "Push notifications",
    description: "Enable browser alerts on this device for lessons, payouts, refunds, and reviews.",
  },
] as const;

function getErrorMessage(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return detail ?? fallback;
}

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function browserSupportsPushNotifications() {
  return (
    typeof window !== "undefined" &&
    "Notification" in window &&
    "serviceWorker" in navigator &&
    "PushManager" in window
  );
}

function urlBase64ToUint8Array(base64String: string) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const normalized = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(normalized);
  const output = new Uint8Array(raw.length);

  for (let index = 0; index < raw.length; index += 1) {
    output[index] = raw.charCodeAt(index);
  }

  return output;
}

async function ensurePushSubscription(publicKey: string): Promise<PushSubscriptionPayload> {
  if (!browserSupportsPushNotifications()) {
    throw new Error("This browser does not support push notifications.");
  }

  if (!publicKey) {
    throw new Error("Push notifications are not configured for this environment yet.");
  }

  const permission = await window.Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error(
      permission === "denied"
        ? "Browser notifications are blocked. Allow them in your browser settings first."
        : "Browser notification permission was not granted."
    );
  }

  const registration = await navigator.serviceWorker.register("/push-sw.js");
  await navigator.serviceWorker.ready;

  const existingSubscription = await registration.pushManager.getSubscription();
  const subscription =
    existingSubscription ??
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    }));

  const serialized = subscription.toJSON();
  if (!serialized.endpoint || !serialized.keys?.p256dh || !serialized.keys?.auth) {
    throw new Error("Could not read the browser push subscription.");
  }

  return {
    endpoint: serialized.endpoint,
    expirationTime:
      typeof serialized.expirationTime === "number"
        ? new Date(serialized.expirationTime).toISOString()
        : null,
    keys: {
      p256dh: serialized.keys.p256dh,
      auth: serialized.keys.auth,
    },
  };
}

async function unsubscribeBrowserPush(): Promise<string | null> {
  if (!browserSupportsPushNotifications()) {
    return null;
  }

  const registration =
    (await navigator.serviceWorker.getRegistration("/push-sw.js")) ??
    (await navigator.serviceWorker.getRegistration());
  const subscription = await registration?.pushManager.getSubscription();
  if (!subscription) {
    return null;
  }

  const endpoint = subscription.endpoint;
  await subscription.unsubscribe();
  return endpoint;
}

export function NotificationCenter() {
  const user = useAuthStore((state) => state.user);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [savingPreferences, setSavingPreferences] = useState(false);
  const [markingAllRead, setMarkingAllRead] = useState(false);
  const [markingId, setMarkingId] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [deliveries, setDeliveries] = useState<NotificationDeliveryItem[]>([]);
  const [preferences, setPreferences] = useState<NotificationPreferences | null>(null);
  const [pushConfig, setPushConfig] = useState<PushConfiguration | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pushBusy, setPushBusy] = useState(false);
  const [pushSupported, setPushSupported] = useState<boolean | null>(null);

  useEffect(() => {
    setPushSupported(browserSupportsPushNotifications());
  }, []);

  useEffect(() => {
    if (!user) {
      return;
    }

    let cancelled = false;

    async function loadUnreadSummary() {
      try {
        const { data } = await apiClient.notifications.list();
        if (!cancelled) {
          setNotifications((data as { items: NotificationItem[] }).items);
          setUnreadCount((data as { unreadCount: number }).unreadCount ?? 0);
        }
      } catch {
        if (!cancelled) {
          setUnreadCount(0);
        }
      }
    }

    void loadUnreadSummary();
    const intervalId = window.setInterval(() => {
      void loadUnreadSummary();
    }, 60000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [user]);

  useEffect(() => {
    if (!open || !user) {
      return;
    }

    let cancelled = false;

    async function loadNotificationCenter() {
      setLoading(true);
      setError(null);
      try {
        const [
          notificationsResponse,
          deliveriesResponse,
          preferencesResponse,
          pushConfigResponse,
        ] = await Promise.all([
          apiClient.notifications.list(),
          apiClient.notifications.listDeliveries(),
          apiClient.notifications.getPreferences(),
          apiClient.notifications.getPushConfig(),
        ]);
        if (cancelled) {
          return;
        }
        setNotifications((notificationsResponse.data as { items: NotificationItem[] }).items);
        setUnreadCount((notificationsResponse.data as { unreadCount: number }).unreadCount ?? 0);
        setDeliveries((deliveriesResponse.data as { items: NotificationDeliveryItem[] }).items ?? []);
        setPreferences(preferencesResponse.data as NotificationPreferences);
        setPushConfig(pushConfigResponse.data as PushConfiguration);
      } catch (err: unknown) {
        if (!cancelled) {
          setError(getErrorMessage(err, "Could not load notifications right now."));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadNotificationCenter();

    return () => {
      cancelled = true;
    };
  }, [open, user]);

  if (!user) {
    return null;
  }

  async function handleMarkRead(notificationId: string) {
    setMarkingId(notificationId);
    setError(null);
    setMessage(null);
    try {
      await apiClient.notifications.markRead(notificationId);
      setNotifications((current) =>
        current.map((notification) =>
          notification.id === notificationId
            ? { ...notification, isRead: true, readAt: new Date().toISOString() }
            : notification
        )
      );
      setUnreadCount((current) => Math.max(0, current - 1));
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Could not mark that notification as read."));
    } finally {
      setMarkingId(null);
    }
  }

  async function handleMarkAllRead() {
    setMarkingAllRead(true);
    setError(null);
    setMessage(null);
    try {
      const { data } = await apiClient.notifications.markAllRead();
      setNotifications((current) =>
        current.map((notification) => ({
          ...notification,
          isRead: true,
          readAt: notification.readAt ?? new Date().toISOString(),
        }))
      );
      setUnreadCount(0);
      setMessage((data as { message?: string }).message ?? "All notifications marked as read.");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Could not mark all notifications as read."));
    } finally {
      setMarkingAllRead(false);
    }
  }

  function togglePreference(key: keyof NotificationPreferences) {
    setPreferences((current) =>
      current
        ? {
            ...current,
            [key]: !current[key],
          }
        : current
    );
  }

  async function handlePushToggle() {
    if (!preferences) {
      return;
    }

    setPushBusy(true);
    setError(null);
    setMessage(null);

    try {
      if (preferences.pushEnabled) {
        const endpoint = await unsubscribeBrowserPush();
        if (endpoint) {
          await apiClient.notifications.unsubscribePush(endpoint);
        }
        const { data } = await apiClient.notifications.updatePreferences({ pushEnabled: false });
        setPreferences(data as NotificationPreferences);
        setPushConfig((current) =>
          current
            ? {
                ...current,
                subscribed: false,
              }
            : current
        );
        setMessage("Push notifications disabled for this browser.");
        return;
      }

      const { data: configData } = await apiClient.notifications.getPushConfig();
      const config = configData as PushConfiguration;
      if (!config.configured || !config.publicKey) {
        throw new Error("Push notifications are not configured for this environment yet.");
      }

      const subscription = await ensurePushSubscription(config.publicKey);
      await apiClient.notifications.subscribePush(subscription);
      const { data } = await apiClient.notifications.updatePreferences({ pushEnabled: true });
      setPreferences(data as NotificationPreferences);
      setPushConfig({
        ...config,
        subscribed: true,
      });
      setMessage("Push notifications enabled for this browser.");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Could not update push notifications right now."));
    } finally {
      setPushBusy(false);
    }
  }

  async function handleSavePreferences() {
    if (!preferences) {
      return;
    }

    setSavingPreferences(true);
    setError(null);
    setMessage(null);
    try {
      const { data } = await apiClient.notifications.updatePreferences(preferences);
      setPreferences(data as NotificationPreferences);
      setMessage("Notification preferences updated.");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Could not save your notification preferences."));
    } finally {
      setSavingPreferences(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={<Button variant="ghost" size="icon-sm" type="button" className="relative" />}
      >
        <BellIcon />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 inline-flex min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-medium text-primary-foreground">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
        <span className="sr-only">Open notifications</span>
      </DialogTrigger>

      <DialogContent className="max-h-[85vh] gap-0 overflow-hidden p-0 sm:max-w-xl">
        <div className="border-b border-border/70 p-4 pr-12">
          <DialogHeader>
            <DialogTitle>Notifications</DialogTitle>
            <DialogDescription>
              Stay on top of bookings, verification reviews, refunds, and payout updates.
            </DialogDescription>
          </DialogHeader>
        </div>

        <Tabs defaultValue="inbox" className="gap-0">
          <TabsList className="mx-4 mt-4">
            <TabsTrigger value="inbox">
              Inbox
              {unreadCount > 0 && <Badge variant="secondary">{unreadCount}</Badge>}
            </TabsTrigger>
            <TabsTrigger value="delivery">Delivery</TabsTrigger>
            <TabsTrigger value="preferences">Preferences</TabsTrigger>
          </TabsList>

          <TabsContent value="inbox" className="space-y-4 px-4 pb-4 pt-4">
            {(message || error) && (
              <div
                className={`rounded-lg border px-3 py-2 text-sm ${
                  error
                    ? "border-destructive/30 bg-destructive/10 text-destructive"
                    : "border-border/70 bg-muted/40 text-foreground"
                }`}
              >
                {error ?? message}
              </div>
            )}

            <div className="flex items-center justify-between gap-3">
              <p className="text-sm text-muted-foreground">
                {unreadCount > 0
                  ? `${unreadCount} unread notification(s)`
                  : "You’re all caught up."}
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={markingAllRead || unreadCount === 0}
                onClick={handleMarkAllRead}
              >
                <CheckCheckIcon />
                {markingAllRead ? "Marking…" : "Mark all read"}
              </Button>
            </div>

            <ScrollArea className="h-[22rem] pr-3">
              <div className="space-y-3">
                {loading ? (
                  <div className="rounded-lg border border-border/70 bg-muted/30 px-3 py-4 text-sm text-muted-foreground">
                    Loading notifications…
                  </div>
                ) : notifications.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-border/70 bg-muted/20 px-3 py-4 text-sm text-muted-foreground">
                    No notifications yet. We’ll show booking and admin activity here as it happens.
                  </div>
                ) : (
                  notifications.map((notification) => (
                    <div
                      key={notification.id}
                      className={`rounded-xl border px-3 py-3 ${
                        notification.isRead
                          ? "border-border/70 bg-background"
                          : "border-primary/20 bg-primary/5"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-medium">{notification.title}</p>
                            <Badge variant={notification.isRead ? "outline" : "secondary"}>
                              {notification.isRead ? "Read" : "Unread"}
                            </Badge>
                          </div>
                          <p className="text-sm text-muted-foreground">{notification.body}</p>
                          <p className="text-xs text-muted-foreground">
                            {formatTimestamp(notification.sentAt)}
                          </p>
                        </div>
                        {!notification.isRead && (
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={markingId === notification.id}
                            onClick={() => void handleMarkRead(notification.id)}
                          >
                            {markingId === notification.id ? "Saving…" : "Mark read"}
                          </Button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
          </TabsContent>

          <TabsContent value="delivery" className="space-y-4 px-4 pb-4 pt-4">
            <ScrollArea className="h-[22rem] pr-3">
              <div className="space-y-3">
                {loading ? (
                  <div className="rounded-lg border border-border/70 bg-muted/30 px-3 py-4 text-sm text-muted-foreground">
                    Loading delivery activity…
                  </div>
                ) : deliveries.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-border/70 bg-muted/20 px-3 py-4 text-sm text-muted-foreground">
                    No delivery activity yet. In-app, email, SMS, and push outcomes will appear here.
                  </div>
                ) : (
                  deliveries.map((delivery) => (
                    <div
                      key={delivery.id}
                      className="rounded-xl border border-border/70 bg-muted/20 px-3 py-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{delivery.title}</p>
                        <Badge variant="outline">{delivery.channel.toUpperCase()}</Badge>
                        <Badge
                          variant={
                            delivery.status === "delivered"
                              ? "secondary"
                              : delivery.status === "skipped"
                                ? "outline"
                                : "destructive"
                          }
                        >
                          {delivery.status}
                        </Badge>
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">{delivery.body}</p>
                      <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                        <p>{formatTimestamp(delivery.attemptedAt)}</p>
                        {delivery.recipient && <p>Recipient: {delivery.recipient}</p>}
                        {delivery.provider && <p>Provider: {delivery.provider}</p>}
                        {delivery.errorMessage && <p>Error: {delivery.errorMessage}</p>}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
          </TabsContent>

          <TabsContent value="preferences" className="space-y-4 px-4 pb-4 pt-4">
            <div className="space-y-3">
              {PREFERENCE_ROWS.map((preference) => {
                const enabled = preferences?.[preference.key] ?? false;
                const isPushPreference = preference.key === "pushEnabled";
                const isDisabled = !preferences || pushBusy;
                const pushUnavailable = isPushPreference && pushConfig && !pushConfig.configured;
                const pushNotSupported = isPushPreference && pushSupported === false;
                const pushBadgeLabel = pushUnavailable
                  ? "Server not configured"
                  : pushNotSupported
                    ? "Browser unsupported"
                    : pushConfig?.subscribed
                      ? "Active subscription"
                      : null;

                return (
                  <div
                    key={preference.key}
                    className="rounded-xl border border-border/70 bg-muted/20 px-3 py-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-medium">{preference.label}</p>
                          {pushBadgeLabel && <Badge variant="outline">{pushBadgeLabel}</Badge>}
                        </div>
                        <p className="text-sm text-muted-foreground">{preference.description}</p>
                        {isPushPreference && (
                          <p className="text-xs text-muted-foreground">
                            {pushUnavailable
                              ? "Add VAPID keys on the backend before enabling push in this environment."
                              : pushNotSupported
                                ? "Use a browser with service worker push support to enable this channel."
                                : "Each browser needs its own subscription before push can be enabled."}
                          </p>
                        )}
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant={enabled ? "default" : "outline"}
                        onClick={() =>
                          isPushPreference
                            ? void handlePushToggle()
                            : togglePreference(preference.key)
                        }
                        disabled={isDisabled || Boolean(pushUnavailable) || Boolean(pushNotSupported)}
                      >
                        {isPushPreference
                          ? pushBusy
                            ? "Updating…"
                            : enabled
                              ? "Disable"
                              : "Enable"
                          : enabled
                            ? "Enabled"
                            : "Off"}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="flex justify-end">
              <Button
                type="button"
                onClick={handleSavePreferences}
                disabled={!preferences || savingPreferences || pushBusy}
              >
                {savingPreferences ? "Saving…" : "Save preferences"}
              </Button>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
