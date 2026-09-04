import { readFile } from "node:fs/promises";
import { ReplitConnectors } from "@replit/connectors-sdk";

const input = JSON.parse(await readFile(0, "utf8"));
const connectors = new ReplitConnectors();

async function readResponse(response, label) {
  let body = {};
  try {
    body = await response.json();
  } catch {
    body = {};
  }
  if (!response.ok) {
    const message = body?.error?.message || `${label} failed (${response.status})`;
    throw new Error(message);
  }
  return body;
}

const profileResponse = await connectors.proxy(
  "google-mail",
  "/gmail/v1/users/me/profile",
  { method: "GET" },
);
const profile = await readResponse(profileResponse, "Gmail profile lookup");
const sender = String(profile.emailAddress || "").trim();
if (!sender) throw new Error("Gmail did not return the connected account email.");

const recipient = String(input.recipient || sender).trim();
const sendResponse = await connectors.proxy(
  "google-mail",
  "/gmail/v1/users/me/messages/send",
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw: input.raw }),
  },
);
const sent = await readResponse(sendResponse, "Gmail send");
console.log(JSON.stringify({ sender, messageId: sent.id || "" }));