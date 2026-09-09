#!/usr/bin/env sh
# The repository's guard rails, applied with the GitHub CLI. Idempotent: run
# it again after any change here and it updates what exists.
#
#   main is owned by the repository admins. Everyone else, collaborators
#   included, opens a pull request; it needs green CI and a merge by an
#   admin. Nobody force-pushes or deletes main.
#
#   The `production` environment carries the deploy secrets and admits only
#   workflow runs on main, so no branch or fork can read them.
#
# Needs: gh authenticated as a repository admin. Rulesets and environment
# branch policies need the repository to be public or on a paid plan.
set -eu

repo="${1:-chessapps/rochade}"

echo "== environment production"
gh api -X PUT "repos/$repo/environments/production" \
  --input - >/dev/null <<'JSON'
{ "deployment_branch_policy": { "protected_branches": false, "custom_branch_policies": true } }
JSON
if ! gh api "repos/$repo/environments/production/deployment-branch-policies" \
     --jq '.branch_policies[].name' | grep -qx main; then
  gh api -X POST "repos/$repo/environments/production/deployment-branch-policies" \
    -f name=main -f type=branch >/dev/null
fi
gh api "repos/$repo/environments/production/deployment-branch-policies" \
  --jq '"   branches allowed: " + ([.branch_policies[].name] | join(", "))'

echo "== ruleset main"
ruleset=$(cat <<'JSON'
{
  "name": "main",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [
    { "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always" }
  ],
  "conditions": { "ref_name": { "include": ["refs/heads/main"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false,
        "allowed_merge_methods": ["merge", "squash", "rebase"]
      } },
    { "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          { "context": "backend" },
          { "context": "frontend" },
          { "context": "contract" }
        ]
      } }
  ]
}
JSON
)
id=$(gh api "repos/$repo/rulesets" --jq '.[] | select(.name=="main") | .id')
if [ -n "$id" ]; then
  printf '%s' "$ruleset" | gh api -X PUT "repos/$repo/rulesets/$id" --input - >/dev/null
  echo "   updated ruleset $id"
else
  id=$(printf '%s' "$ruleset" | gh api -X POST "repos/$repo/rulesets" --input - --jq .id)
  echo "   created ruleset $id"
fi

echo "== repository"
gh api -X PATCH "repos/$repo" -F allow_auto_merge=false -F delete_branch_on_merge=true >/dev/null
echo "   auto-merge off, merged branches deleted"

echo "== secrets on production (names only; values are write-only)"
gh secret list --repo "$repo" --env production
