# Phase 01 — Host

Target: Oracle Cloud Always Free, ARM, India region. Fallback: E2E Networks C3.

Measured requirement: **2.29 GB peak RAM** (model + index + one live query).

## Checklist — Oracle (first choice, ₹0)

- [ ] Sign up at `cloud.oracle.com/free` (card for identity verification only)
- [ ] **Home region = India West (Mumbai) or India South (Hyderabad)** — permanent, cannot be changed
- [ ] Create instance: shape `VM.Standard.A1.Flex`
- [ ] **Exactly 2 OCPU / 12 GB** (see quota maths below)
- [ ] Image: Ubuntu 22.04 (not 24.04, not 26.04)
- [ ] Upload SSH public key
- [ ] Note the public IP
- [ ] VCN security list: ingress rule TCP 8501 from 0.0.0.0/0
- [ ] On the VM: `sudo iptables -I INPUT -p tcp --dport 8501 -j ACCEPT && sudo netfilter-persistent save`
- [ ] Confirm SSH works: `ssh ubuntu@<ip>`

## Fallback — E2E Networks (Rs 2,263/month)

- [ ] Complete KYC (start early — verification can take hours)
- [ ] C3, 4 vCPU / 8 GB / 100 GB SSD, Ubuntu 22.04, **On-Demand** (no long commitment)
- [ ] Open port 8501

## Challenges

**"Out of host capacity" is the likely failure.** Always Free ARM is heavily contended,
especially in Indian regions. Mitigations: try each Availability Domain in the region;
retry over several days; upgrading to Pay-As-You-Go improves capacity priority while
Always Free resources stay free.

**The quota maths matters.** Always Free ARM gives 1,500 OCPU-hours and 9,000 GB-hours per
month. A month is ~730 hours, so 24/7 operation caps you at 2 OCPU (1,460 hrs) and 12 GB
(8,760 GB-hrs). **Take 4 OCPU and you exhaust the quota in ~15 days** and the instance
stops or starts billing mid-month.

**Oracle's port trap.** Its images ship an iptables ruleset that ignores the VCN security
list. Configure both or the app runs fine and appears completely dead from outside. This
catches nearly everyone.

**Home region is permanent.** Choosing a non-India region by accident cannot be undone
without a new tenancy.

**Free tier is not an SLA.** Oracle can reclaim idle Always Free instances. Acceptable for
a pilot; if this becomes the official AP-facing service, budget the E2E fallback.

**E1 on E2E is a trap** — it forces 150 GB root storage at Rs 1,500/month and has no
default public IP, so its 72% instance discount evaporates. C3 bundles 100 GB and wins.
