#!/bin/python3

'''
Assumptions:
    - Using GitPython module, the first element in the list of git.objects.commit.Commit.parents is the first parent of Git program.
'''


# pylint: disable=invalid-name


# builtin modules
from typing import List

import argparse
import datetime
import os
import tempfile


# third-party modules
import git


def find_lca(
    ref1: git.objects.commit.Commit,
    ref2: git.objects.commit.Commit
) -> git.objects.commit.Commit:
    '''Returns some least common ancestor (LCA) of two commits.'''

    # This is the trivial case of finding LCA of the same vertex.
    if ref1.binsha == ref2.binsha:
        return ref1

    ancestors1 = set([ref1.binsha])  # the ancestors of commit obj `ref1`
    ancestors2 = set([ref2.binsha])  # the ancestors of commit obj `ref2`
    last1 = ref1  # the last visited ancestor (commit obj) of `ref1`)
    last2 = ref2  # the last visited ancestor (commit obj) of `ref2`)

    while True:
        # Extend the range of ancestors of `ref1` and see if we find the LCA.
        for _ in range(len(ancestors1)):
            if len(last1.parents) == 0:
                break
            # We only concern with the primary parent of a commit.
            last1 = last1.parents[0]
            if last1.binsha in ancestors2:
                return last1
            ancestors1.add(last1.binsha)
        # Extend the range of ancestors of `ref2` and see if we find the LCA.
        for _ in range(len(ancestors2)):
            if len(last2.parents) == 0:
                break
            # We only concern with the primary parent of a commit.
            last2 = last2.parents[0]
            if last2.binsha in ancestors1:
                return last2
            ancestors2.add(last2.binsha)


# TODO: docstring
def find_root(
    commit_list: List[git.objects.commit.Commit]
) -> git.objects.commit.Commit:

    # Assume that there is at least one commit object to consider.
    assert len(commit_list) >= 1

    root = commit_list[0]
    for c in commit_list[1:]:
        root = find_lca(root, c)
    return root


# TODO: docstring
def find_relevant_commits(
    commit_list: List[git.objects.commit.Commit]
) -> List[git.objects.commit.Commit]:
    shaset = set()  # a set of commit shasum for uniqueness of added commits
    render_commits = {}  # a map from shasum to commits to be rendered

    for c in commit_list:
        if c.binsha in shaset:
            continue
        shaset.add(c.binsha)
        render_commits[c.binsha] = c

    for i, c1 in enumerate(commit_list):
        for j, c2 in enumerate(commit_list):
            if i == j:
                continue
            lca = find_lca(c1, c2)
            if lca.binsha in shaset:
                continue
            shaset.add(lca.binsha)
            render_commits[lca.binsha] = lca

    return render_commits


def copy_commit(
    repo: git.repo.base.Repo,
    commit: git.objects.commit.Commit,
    message: str
) -> None:
    repo.index.commit(
        message=message,
        # We keep both author_date and commit_date since we do not know which
        # Git uses when ordering the commit nodes in the git log.
        author_date=datetime.datetime.fromtimestamp(
            commit.authored_date,
            tz=datetime.timezone(
                datetime.timedelta(seconds=commit.author_tz_offset))),
        commit_date=datetime.datetime.fromtimestamp(
            commit.committed_date,
            tz=datetime.timezone(
                datetime.timedelta(seconds=commit.committer_tz_offset))))


# TODO: docstring, typing
def get_abbrev_log_graph(
    repo: git.repo.base.Repo,
    head_names: List[str]
) -> str:
    # The following are special strings added to commit message for log graph postprocessing.

    class RefHeadName:
        PREFIX = 'REF_HEAD'
        ref_head_cnt = 0

        @classmethod
        def new(cls):
            cls.ref_head_cnt += 1
            return f'{cls.PREFIX}_{cls.ref_head_cnt}'

    COMMIT_ABBREV = 'COMMIT_TYPE1'
    COMMIT_REGULAR = 'COMMIT_TYPE2'
    COMMIT_HEAD = 'COMMIT_TYPE3'
    COMMIT_TAG_LEN = len(COMMIT_ABBREV)

    # a list of GitPython commit objects correspnding to commits in `head_names`
    heads = [repo.commit(x) for x in head_names]

    # a map from shasum to commits to be rendered
    render_commits = find_relevant_commits(heads)

    # the faux repo for abbrev commit graph
    with tempfile.TemporaryDirectory() as tmpdir:
        faux_repo = git.Repo.init(tmpdir)

        # a map from shasums of commits needing render to shasum in faux repo
        created = {}

        # Create root commit.
        root = find_root(heads)
        root_shortsha = repo.git.rev_parse(root.hexsha, short=True)
        root_type = COMMIT_HEAD if root in heads else COMMIT_REGULAR
        root_decor = repo.git.log(root.hexsha, '--decorate', '-1') \
            .splitlines()[0][len('commit ') + len(root.hexsha):]
        copy_commit(faux_repo, root,
            f'{root_type} {root_shortsha} {root.message}{root_decor}')
        created[root.binsha] = faux_repo.commit('HEAD')

        # Create branch one by one for each head (commits of interest).
        for head in heads:
            # Find one branch.
            new_growth = []  # the commits to be rendered on this branch
            abbrev_nums = []  # the number of abbreviation for each commit
            abbrev_num = 0  # the number of abbreviation since last
            c = head  # the current commit that we inspect
            while True:
                if c.binsha in render_commits:
                    new_growth.append(c)
                    # The -1 is needed because the added commit is counted.
                    abbrev_nums.append(abbrev_num - 1)
                    abbrev_num = 0
                if c.binsha in created:
                    break
                # We only concern with the primary parent of a commit.
                c = c.parents[0]
                abbrev_num += 1
            new_growth.reverse()
            abbrev_nums.reverse()

            # Create this branch.
            # Check out to the commit where this branch is added.
            budding_point = created[new_growth[0].binsha]
            branch_name = RefHeadName.new()
            faux_repo.create_head(branch_name, str(budding_point))
            faux_repo.git.checkout(branch_name)
            for c, abbrev_num in zip(new_growth[1:], abbrev_nums):
                # Print the part that counts the number of commit abbreviations.
                if abbrev_num > 0:
                    copy_commit(faux_repo, c, f'{COMMIT_ABBREV}')
                    copy_commit(faux_repo, c,
                        f'{COMMIT_ABBREV} [{abbrev_num} commit(s) abbreviated]')
                    copy_commit(faux_repo, c, f'{COMMIT_ABBREV}')
                # Print the actual commit of interest.
                c_type = COMMIT_HEAD if c in heads else COMMIT_REGULAR
                c_shortsha = repo.git.rev_parse(c.hexsha, short=True)
                c_decor = repo.git.log(c.hexsha, '--decorate', '-1') \
                    .splitlines()[0][len('commit ') + len(c.hexsha):]
                copy_commit(faux_repo, c,
                    f'{c_type} {c_shortsha} {c.summary}{c_decor}')
                created[c.binsha] = faux_repo.commit('HEAD')

        abbrev_log = faux_repo.git.log(
            '--all',
            '--no-decorate',
            '--graph',
            '--oneline',
            '--no-abbrev-commit')

    # Postprocess the abbreviated graph.
    postproc_lines = []  # the lines of abbrev. graph after post-processing
    for line in abbrev_log.splitlines():
        prefix_end = line.find('COMMIT_')
        if prefix_end == -1:
            postproc_lines.append(line)
            continue

        # Find the begin and end of shasum and 'COMMIT_' postprocessing string.
        prefix_end += COMMIT_TAG_LEN + 1
        prefix_start = prefix_end - (COMMIT_TAG_LEN + len(root.hexsha) + 2)
        
        prefix = line[prefix_start:prefix_end]
        noprefix = line[:prefix_start] + line[prefix_end:]

        # Change the commit node based on the commit type.
        if COMMIT_ABBREV in prefix:
            noprefix = noprefix.replace('*', '|', 1)
        elif COMMIT_HEAD in prefix:
            noprefix = noprefix.replace('*', '@', 1)
        postproc_lines.append(noprefix)

    return '\n'.join(postproc_lines)


def main():
    parser = argparse.ArgumentParser(
        description='Displays an abbreviated git log graph containing all specified commit references.')
    parser.add_argument('commit_refs', nargs='+', type=str)

    args = parser.parse_args()

    repo = git.Repo(os.getcwd(), search_parent_directories=True)

    print(get_abbrev_log_graph(repo, args.commit_refs))


if __name__ == '__main__':
    main()
