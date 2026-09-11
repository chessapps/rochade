/**
 * The switch that makes a tournament public. Off by default; on, it is
 * readable by anyone at /live/<slug>. The slug is chosen from the name the
 * first time and kept, so a link that was posted keeps working after the
 * tournament is hidden and shown again.
 */

import { useEffect, useState, type FormEvent } from "react";

import { errorMessage } from "../api";
import { usePublishTournament } from "../queries";
import { Dialog } from "./Dialog";
import { useToast } from "./Toast";
import { Banner, Button, Field, Input } from "./ui";

export function publicUrl(slug: string): string {
  return `${window.location.origin}/live/${slug}`;
}

export function PublishDialog({
  open,
  onClose,
  tournament,
}: {
  open: boolean;
  onClose: () => void;
  tournament: { id: string; name: string; published: boolean; slug: string | null };
}) {
  const publish = usePublishTournament();
  const toast = useToast();
  const [slug, setSlug] = useState(tournament.slug ?? "");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (open) {
      setSlug(tournament.slug ?? "");
      setCopied(false);
    }
  }, [open, tournament.slug]);

  const run = (published: boolean) => {
    const wanted = slug.trim();
    publish.mutate(
      {
        tournamentId: tournament.id,
        published,
        // Sending no slug lets the API derive one from the name on first publication.
        slug: wanted && wanted !== tournament.slug ? wanted : null,
      },
      {
        onSuccess: (result) => {
          setSlug(result.slug ?? "");
          toast.success(
            published ? `${tournament.name} is public.` : `${tournament.name} is hidden again.`,
          );
          if (!published) onClose();
        },
      },
    );
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    run(true);
  };

  const link = tournament.slug ? publicUrl(tournament.slug) : null;
  const copy = () => {
    if (!link) return;
    void navigator.clipboard?.writeText(link).then(
      () => {
        setCopied(true);
        toast.success("Link copied.");
      },
      () => toast.error("Could not copy the link."),
    );
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={tournament.published ? "Public" : "Publish this tournament"}
      subtitle={
        tournament.published
          ? "Anyone with the link sees pairings, results and standings."
          : "Until you publish, nobody outside the desk can see it."
      }
      busy={publish.isPending}
      footer={
        <>
          <Button onClick={onClose} disabled={publish.isPending}>
            Close
          </Button>
          {tournament.published && (
            <Button tone="danger" onClick={() => run(false)} busy={publish.isPending}>
              Hide
            </Button>
          )}
          <Button form="publish-tournament" type="submit" tone="primary" busy={publish.isPending}>
            {tournament.published ? "Save" : "Publish"}
          </Button>
        </>
      }
    >
      <form id="publish-tournament" onSubmit={submit} className="flex flex-col gap-3">
        <Field
          label="Address"
          hint={
            tournament.published
              ? "Lower-case letters, digits and dashes. Changing it breaks the link already shared."
              : "Lower-case letters, digits and dashes. Leave it empty to take one from the name."
          }
        >
          <div className="flex items-center gap-1">
            <span className="shrink-0 font-mono text-body-sm text-ink-3">/live/</span>
            <Input
              value={slug}
              onChange={(event) => setSlug(event.target.value)}
              placeholder={tournament.published ? "" : "from the name"}
              aria-label="public address"
              className="flex-1"
            />
          </div>
        </Field>
        {link && tournament.published && (
          <div className="flex flex-wrap items-center gap-2 rounded-md border border-emerald-line bg-emerald-soft px-3 py-2 text-body-sm text-emerald-text">
            <a href={link} target="_blank" rel="noreferrer" className="font-mono underline">
              {link}
            </a>
            <Button size="sm" onClick={copy}>
              {copied ? "Copied" : "Copy link"}
            </Button>
          </div>
        )}
        <p className="text-body-sm text-ink-2">
          The public page shows every section: the pairings of each round, results as they
          come in, marked preliminary until you confirm them or release the round, the
          standings, and every game of a player. Nothing else: no phones, no codes.
        </p>
        {publish.isError && <Banner tone="error">{errorMessage(publish.error)}</Banner>}
      </form>
    </Dialog>
  );
}
