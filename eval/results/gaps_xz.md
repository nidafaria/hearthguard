# Visibility gaps, ecosystem_xz

Signals come from the cached records only. xz-devel is a place in the graph but has no signals here. xz-git has only the commits that carry the identity behind the Debian request. Gaps are therefore a lower bound.

Decisions computed: 4, not computed: 0. Gap rows: 22 (21 UNREACHABLE, 1 UNNOTICED). Label confidence: absence-of-evidence 20, close-call 1, high 1.

| Decision | Place | Deciding role | Status | Gap | Signal | Signal at (UTC) | Label |
|---|---|---|---|---|---|---|---|
| oss-fuzz-build-change-pr10667 | oss-fuzz | oss-fuzz reviewer | COMPUTED | UNREACHABLE | pr_opened in oss-fuzz | 2023-03-20T14:45:31Z | close-call |
| oss-fuzz-build-change-pr10667 | oss-fuzz | oss-fuzz reviewer | COMPUTED | UNNOTICED | commit in oss-fuzz | 2023-03-20T15:21:06Z | high |
| kernel-maintainer-entry-lkml-2024-3-20-1008 | lkml | Linux kernel reviewer | COMPUTED | UNREACHABLE | pr_opened in oss-fuzz | 2023-03-20T14:45:31Z | absence-of-evidence |
| kernel-maintainer-entry-lkml-2024-3-20-1008 | lkml | Linux kernel reviewer | COMPUTED | UNREACHABLE | commit in oss-fuzz | 2023-03-20T15:21:06Z | absence-of-evidence |
| kernel-maintainer-entry-lkml-2024-3-20-1008 | lkml | Linux kernel reviewer | COMPUTED | UNREACHABLE | pr_opened in oss-fuzz | 2023-07-07T13:49:31Z | absence-of-evidence |
| kernel-maintainer-entry-lkml-2024-3-20-1008 | lkml | Linux kernel reviewer | COMPUTED | UNREACHABLE | commit in oss-fuzz | 2023-07-07T14:01:15Z | absence-of-evidence |
| kernel-maintainer-entry-lkml-2024-3-20-1008 | lkml | Linux kernel reviewer | COMPUTED | UNREACHABLE | commit_applied in xz-git | 2023-10-13T12:54:05Z | absence-of-evidence |
| kernel-maintainer-entry-lkml-2024-3-20-1008 | lkml | Linux kernel reviewer | COMPUTED | UNREACHABLE | commit_applied in xz-git | 2023-10-13T12:54:05Z | absence-of-evidence |
| kernel-maintainer-entry-lkml-2024-3-20-1008 | lkml | Linux kernel reviewer | COMPUTED | UNREACHABLE | commit_applied in xz-git | 2023-10-13T12:54:05Z | absence-of-evidence |
| debian-upgrade-request-bug1067708 | debian-bts | Debian package maintainer | COMPUTED | UNREACHABLE | commit in xz-git | 2023-06-27T12:33:15Z | absence-of-evidence |
| debian-upgrade-request-bug1067708 | debian-bts | Debian package maintainer | COMPUTED | UNREACHABLE | commit in xz-git | 2023-06-27T12:33:15Z | absence-of-evidence |
| debian-upgrade-request-bug1067708 | debian-bts | Debian package maintainer | COMPUTED | UNREACHABLE | commit in xz-git | 2023-10-13T12:54:05Z | absence-of-evidence |
| debian-upgrade-request-bug1067708 | debian-bts | Debian package maintainer | COMPUTED | UNREACHABLE | commit in xz-git | 2023-10-13T12:54:05Z | absence-of-evidence |
| debian-upgrade-request-bug1067708 | debian-bts | Debian package maintainer | COMPUTED | UNREACHABLE | commit in xz-git | 2023-10-13T12:54:05Z | absence-of-evidence |
| launchpad-upgrade-request-bug2059417 | launchpad | Ubuntu developer | COMPUTED | UNREACHABLE | pr_opened in oss-fuzz | 2023-03-20T14:45:31Z | absence-of-evidence |
| launchpad-upgrade-request-bug2059417 | launchpad | Ubuntu developer | COMPUTED | UNREACHABLE | commit in oss-fuzz | 2023-03-20T15:21:06Z | absence-of-evidence |
| launchpad-upgrade-request-bug2059417 | launchpad | Ubuntu developer | COMPUTED | UNREACHABLE | pr_opened in oss-fuzz | 2023-07-07T13:49:31Z | absence-of-evidence |
| launchpad-upgrade-request-bug2059417 | launchpad | Ubuntu developer | COMPUTED | UNREACHABLE | commit in oss-fuzz | 2023-07-07T14:01:15Z | absence-of-evidence |
| launchpad-upgrade-request-bug2059417 | launchpad | Ubuntu developer | COMPUTED | UNREACHABLE | commit_applied in xz-git | 2023-10-13T12:54:05Z | absence-of-evidence |
| launchpad-upgrade-request-bug2059417 | launchpad | Ubuntu developer | COMPUTED | UNREACHABLE | commit_applied in xz-git | 2023-10-13T12:54:05Z | absence-of-evidence |
| launchpad-upgrade-request-bug2059417 | launchpad | Ubuntu developer | COMPUTED | UNREACHABLE | commit_applied in xz-git | 2023-10-13T12:54:05Z | absence-of-evidence |
| launchpad-upgrade-request-bug2059417 | launchpad | Ubuntu developer | COMPUTED | UNREACHABLE | reviewed_by_tag in lkml | 2024-03-20T18:38:34Z | absence-of-evidence |

Reading the labels: UNREACHABLE: no loaded record shows the deciding role acting in the signal's place before the signal. This is absence of evidence, not proof the role was not watching. UNNOTICED: the role is evidenced in the place before the signal, and the decision does not reference the signal. A decision references the signals of its own record and of records its request text cites; nothing else.
