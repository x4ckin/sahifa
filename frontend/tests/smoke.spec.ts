import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import App from "../src/App.vue";
import { makeRouter } from "../src/router";

describe("app", () => {
  it("mounts the app with the home route", async () => {
    const router = makeRouter();
    await router.push("/");
    const wrapper = mount(App, { global: { plugins: [router], stubs: { Home: { template: "<div class='home-stub' />" } } } });
    await flushPromises();
    expect(wrapper.find("[data-app]").exists()).toBe(true);
    expect(router.currentRoute.value.name).toBe("home");
  });
});
