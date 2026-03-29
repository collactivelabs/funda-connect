self.addEventListener("push", (event) => {
  const payload = event.data ? event.data.json() : {};
  const title = payload.title || "FundaConnect";
  const body = payload.body || "You have a new update.";
  const data = payload.data || {};
  const url = payload.url || data.url || "/";

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      data: { ...data, url },
      icon: "/favicon.ico",
      badge: "/favicon.ico",
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const targetUrl = event.notification.data?.url || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ("focus" in client) {
          client.postMessage?.({ type: "fundaconnect-push-click", url: targetUrl });
          return client.focus();
        }
      }

      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }

      return undefined;
    })
  );
});
