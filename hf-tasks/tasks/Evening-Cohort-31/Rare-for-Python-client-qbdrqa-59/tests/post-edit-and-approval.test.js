import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { ApplicationViews } from "../views/ApplicationViews";
import { PostForm } from "../components/posts/PostForm";
import { UnapprovedPosts } from "../components/admin/UnapprovedPosts";
import * as PostManager from "../managers/PostManager";
import * as TagManager from "../managers/TagManager";

jest.mock("../managers/PostManager");
jest.mock("../managers/TagManager");

const mockPost = {
  id: 44,
  title: "Editing Title",
  content: "Some content",
  category: { id: 2, label: "Work" },
  image_url: "",
  tags: [{ id: 7, label: "Tech" }],
  user: { id: 99, username: "owner" }
};

describe("post editing route and form behavior", () => {
  beforeEach(() => {
    localStorage.setItem("auth_token", "99");
    PostManager.getPostById.mockResolvedValue({
      status: 200,
      response: Promise.resolve(mockPost)
    });
    TagManager.getAllTags.mockResolvedValue({
      status: 200,
      response: Promise.resolve([{ id: 7, label: "Tech" }])
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  test("routes to new edit path and shows edit subtitle", async () => {
    render(
      <MemoryRouter initialEntries={["/post/edit/44"]}>
        <ApplicationViews token="99" setToken={() => {}} />
      </MemoryRouter>
    );

    expect(await screen.findByText("Edit Post")).toBeInTheDocument();
    expect(screen.getByText("Rare Publishing")).toBeInTheDocument();
  });

  test("PostForm in edit mode loads existing post data", async () => {
    render(
      <MemoryRouter initialEntries={["/post/edit/44"]}>
        <Routes>
          <Route path="/post/edit/:id" element={<PostForm editMode edit />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(PostManager.getPostById).toHaveBeenCalled();
    });

    const calledWith = PostManager.getPostById.mock.calls[0][0];
    expect(String(calledWith)).toBe("44");
    expect(TagManager.getAllTags).toHaveBeenCalled();
  });
});

describe("unapproved post approval flow", () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  test("shows loading skeleton after approval starts", async () => {
    PostManager.getUnapprovedPosts.mockResolvedValue({
      json: () => Promise.resolve([
        {
          id: 1,
          title: "Pending Post",
          content: "Needs approval",
          category: { label: "Life" },
          user: { username: "author" },
          image_url: ""
        }
      ])
    });

    let resolveApprove;
    const approvePromise = new Promise((resolve) => {
      resolveApprove = resolve;
    });
    PostManager.approvePost.mockReturnValue(approvePromise);

    render(<UnapprovedPosts />);

    expect(await screen.findByText("Pending Post")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => {
      expect(document.querySelectorAll(".is-skeleton").length).toBeGreaterThan(0);
    });

    expect(PostManager.approvePost).toHaveBeenCalledWith(1);
    resolveApprove();
  });
});
