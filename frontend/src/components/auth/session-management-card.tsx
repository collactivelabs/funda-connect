"use client";

import { useState } from "react";
import type { AuthSession } from "@/types";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiClient } from "@/lib/api";
import { useAuthStore } from "@/stores/auth.store";

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatDeviceLabel(session: AuthSession) {
  const agent = session.userAgent?.trim();
  if (!agent) {
    return session.current ? "Current browser session" : "Browser session";
  }
  return agent.length > 110 ? `${agent.slice(0, 107)}...` : agent;
}

function getErrorMessage(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return detail ?? fallback;
}

export function SessionManagementCard() {
  const user = useAuthStore((state) => state.user);
  const [sessions, setSessions] = useState<AuthSession[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [revokingOthers, setRevokingOthers] = useState(false);
  const [busySessionId, setBusySessionId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!user) {
    return null;
  }

  const otherSessionCount = sessions?.filter((session) => !session.current).length ?? 0;

  async function loadSessions() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const { data } = await apiClient.auth.listSessions();
      setSessions(data);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Could not load active sessions."));
    } finally {
      setLoading(false);
    }
  }

  async function handleRevokeSession(sessionId: string) {
    setBusySessionId(sessionId);
    setError(null);
    setMessage(null);
    try {
      const { data } = await apiClient.auth.revokeSession(sessionId);
      setSessions((current) => current?.filter((session) => session.id !== sessionId) ?? []);
      setMessage((data as { message?: string }).message ?? "Session revoked.");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Could not revoke that session."));
    } finally {
      setBusySessionId(null);
    }
  }

  async function handleRevokeOthers() {
    setRevokingOthers(true);
    setError(null);
    setMessage(null);
    try {
      const { data } = await apiClient.auth.revokeOtherSessions();
      setSessions((current) => current?.filter((session) => session.current) ?? []);
      setMessage((data as { message?: string }).message ?? "Other sessions revoked.");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Could not revoke the other sessions."));
    } finally {
      setRevokingOthers(false);
    }
  }

  return (
    <Card className="mb-6">
      <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <CardTitle>Active Sessions</CardTitle>
          <CardDescription>
            Review where your account is signed in and revoke any older browser sessions.
          </CardDescription>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={loadSessions} disabled={loading}>
          {loading ? "Loading…" : sessions ? "Refresh sessions" : "View sessions"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {(message || error) && (
          <Alert variant={error ? "destructive" : "default"}>
            <AlertDescription>{error ?? message}</AlertDescription>
          </Alert>
        )}

        {sessions === null ? (
          <p className="text-sm text-muted-foreground">
            Load your active sessions to see where this account is signed in.
          </p>
        ) : sessions.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No active sessions were found for this account.
          </p>
        ) : (
          <div className="space-y-3">
            {sessions.map((session) => (
              <div
                key={session.id}
                className="rounded-lg border border-border/70 bg-muted/30 p-3"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{formatDeviceLabel(session)}</span>
                      {session.current ? (
                        <Badge variant="secondary">Current</Badge>
                      ) : (
                        <Badge variant="outline">Active</Badge>
                      )}
                    </div>
                    <div className="space-y-1 text-sm text-muted-foreground">
                      <p>Last seen: {formatTimestamp(session.lastSeenAt)}</p>
                      <p>Signed in: {formatTimestamp(session.createdAt)}</p>
                      <p>Expires: {formatTimestamp(session.expiresAt)}</p>
                      {session.ipAddress && <p>IP: {session.ipAddress}</p>}
                    </div>
                  </div>

                  {!session.current && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={busySessionId === session.id}
                      onClick={() => handleRevokeSession(session.id)}
                    >
                      {busySessionId === session.id ? "Revoking…" : "Revoke"}
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {sessions && sessions.length > 0 && (
          <div className="flex flex-col gap-3 border-t border-border/70 pt-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">
              {otherSessionCount > 0
                ? `${otherSessionCount} other active session(s) found.`
                : "Only your current browser session is active."}
            </p>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={otherSessionCount === 0 || revokingOthers}
              onClick={handleRevokeOthers}
            >
              {revokingOthers ? "Revoking…" : "Sign out other sessions"}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
