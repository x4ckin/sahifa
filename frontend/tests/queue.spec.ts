import { describe, expect, it } from "vitest";

import { ApiError } from "../src/api";
import { createQueue } from "../src/upload/queue";

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => ((resolve = res), (reject = rej)));
  return { promise, resolve, reject };
}
const file = (name: string) => new File(["x"], name, { type: "image/jpeg" });
const tick = () => new Promise((r) => setTimeout(r, 0));

describe("upload queue", () => {
  it("never runs more than two uploads at once", async () => {
    const pending: ReturnType<typeof deferred<{ token: string; kind: string }>>[] = [];
    let running = 0;
    let peak = 0;
    const q = createQueue(async () => {
      running++;
      peak = Math.max(peak, running);
      const d = deferred<{ token: string; kind: string }>();
      pending.push(d);
      try {
        return await d.promise;
      } finally {
        running--;
      }
    });
    q.add([file("a"), file("b"), file("c"), file("d")]);
    await tick();
    expect(running).toBe(2);
    while (pending.length) {
      pending.shift()!.resolve({ token: "t", kind: "image" });
      await tick();
      await tick();
    }
    expect(peak).toBe(2);
    expect(q.items.value.every((i) => i.state === "done")).toBe(true);
  });

  it("one failed upload does not stop the queue", async () => {
    const q = createQueue(async (f, onProgress) => {
      onProgress(1);
      if (f.name === "b") throw new ApiError("start_bot", 409);
      return { token: `T-${f.name}`, kind: "image" };
    });
    q.add([file("a"), file("b"), file("c")]);
    await q.idle();
    const byName = Object.fromEntries(q.items.value.map((i) => [i.file.name, i]));
    expect(byName.a.state).toBe("done");
    expect(byName.c.result).toEqual({ token: "T-c", kind: "image" });
    expect(byName.b.state).toBe("error");
    expect(byName.b.error).toBe("start_bot");
  });

  it("retry re-sends a failed item", async () => {
    let fail = true;
    const q = createQueue(async () => {
      if (fail) throw new ApiError("network", 0);
      return { token: "ok", kind: "image" };
    });
    q.add([file("a")]);
    await q.idle();
    fail = false;
    q.retry(q.items.value[0].id);
    await q.idle();
    expect(q.items.value[0].state).toBe("done");
  });

  it("calls onDone in the order files were added, even if they finish out of order", async () => {
    const order: string[] = [];
    const slow = deferred<{ token: string; kind: string }>();
    const q = createQueue(
      async (f) => (f.name === "a" ? slow.promise : { token: f.name, kind: "image" }),
      2,
      (item) => order.push(item.file.name),
    );
    q.add([file("a"), file("b")]);
    await tick();
    slow.resolve({ token: "a", kind: "image" });
    await q.idle();
    expect(order).toEqual(["a", "b"]);
  });
});
