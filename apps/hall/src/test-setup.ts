import "@testing-library/jest-dom/vitest";
// jsdom has no IndexedDB, and the queue and board cache live there.
import "fake-indexeddb/auto";
