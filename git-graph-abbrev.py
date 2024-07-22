# pylint: disable=invalid-name

import tempfile

import git

# Assumptions:
#   - Using GitPython module, the first element in the list of git.objects.commit.Commit.parents is the first parent of Git program.

TEST_REPO_PATH = ''
TEST_REF1 = 'master'
TEST_REF2 = 'br'

TEST_REPO_PATH = ''
TEST_REF1 = 'v6.6.3'
TEST_REF2 = 'dev'
TEST_REF3 = 'v6.7.2'


class DiGraph:
    class Vertex:
        def __init__(self, my_id, extra):
            self.id = my_id
            self.extra = extra

    def __init__(self):
        self.vertices = {}  # a map from vertex ID to each Vertex
        self.adjlist = {}  # a map from vertex ID to the neighbour vertices IDs

    def arc_add(self, u, v):
        pass

    def vertex_add(self, v):
        pass

class DFS:
    def __init__(self, graph: DiGraph):
        self._graph = graph
        self._visit = set()

    def algo_dfs(self, start_id):
        assert start_id not in self._visit

        # CUSTOM POINT: entry

        self._visit.add(start_id)

        for next_id in self._graph.adjlist[start_id]:
            if next_id in self._visit:
                continue
            self.algo_dfs(next_id)

        # CUSTOM POINT: exit



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
    commit_list: list[git.objects.commit.Commit]
) -> git.objects.commit.Commit:

    # Assume that there is at least one commit object to consider.
    assert len(commit_list) >= 1

    root = commit_list[0]
    print(f'root = {root}')
    for c in commit_list[1:]:
        print(f'c = {c}')
        root = find_lca(root, c)
        print(f'root = {root}')
    return root


# TODO: docstring
def find_relevant_commits(
    commit_list: list[git.objects.commit.Commit]
) -> list[git.objects.commit.Commit]:
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


# TODO: docstring, typing
def get_abbrev_log_graph(
    heads: list[git.objects.commit.Commit],
    main_head: git.objects.commit.Commit
) -> str:
    # The following are special strings added to commit message for log graph postprocessing.

    class RefHeadName:
        PREFIX = 'REF_HEAD'
        ref_head_cnt = 0

        @classmethod
        def new(cls):
            cls.ref_head_cnt += 1
            return f'{cls.PREFIX}_{cls.ref_head_cnt}'

    COMMIT_ABBREV = 'COMMIT_ABBREV'
    COMMIT_REGULAR = 'COMMIT_REGULAR'

    # a map from shasum to commits to be rendered
    render_commits = find_relevant_commits(heads)

    # the faux repo for abbrev commit graph
    # TODO: automatically delete after debugging
    faux_repo = git.Repo.init(tempfile.TemporaryDirectory().name)
    print(faux_repo.working_dir)

    # a map from shasums of commits to be rendered to shasum in faux repo
    created = {}

    # Create root commit.
    faux_repo.index.commit(f'{COMMIT_REGULAR} root {str(root)}')
    created[root.binsha] = faux_repo.commit('HEAD')

    # Create branch one by one for each head (commits of interest).
    for head in heads:
        # Find one branch.
        new_growth = []  # the commits to be rendered on this branch
        c = head
        while True:
            if c.binsha in render_commits:
                new_growth.append(c)
            if c.binsha in created:
                break
            # We only concern with the primary parent of a commit.
            c = c.parents[0]
        new_growth.reverse()

        print()
        for c in new_growth:
            print(c)
        print()

        # Create this branch.
        # Check out to the commit where this branch is added.
        budding_point = created[new_growth[0].binsha]
        branch_name = RefHeadName.new()
        faux_repo.create_head(branch_name, str(budding_point))
        faux_repo.git.checkout(branch_name)
        input()
        for c in new_growth[1:]:
            faux_repo.index.commit(f'{COMMIT_ABBREV}')
            faux_repo.index.commit(f'{COMMIT_REGULAR} {c}')
            created[c.binsha] = faux_repo.commit('HEAD')



if __name__ == '__main__':
    repo = git.Repo(TEST_REPO_PATH)

    master = repo.commit(TEST_REF1)
    br = repo.commit(TEST_REF2)
    test = repo.commit(TEST_REF3)

    all_commits = find_relevant_commits([master, br, test])
    for c in all_commits:
        print(all_commits[c])
    print()

    root = find_root([master, br, test])
    print(root)
    print()

    get_abbrev_log_graph([master, br, test], master)

    # Find all the "branch-off" commits (some LCA of other commits) and leaves.
    # These commits are to be rendered in the final abbreviated graph.


    # Create a faux repo just to represent the abbreviated parent-child relationship of the commits to be rendered.

    # Render the abbreviated graph.

    # Postprocess the abbreviated graph.

