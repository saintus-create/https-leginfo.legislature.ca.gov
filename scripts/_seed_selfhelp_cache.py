#!/usr/bin/env python3
"""Seed data/selfhelp/cache with markdown content for core Self-Help Guide pages.

These were captured from https://selfhelp.courts.ca.gov/ via the platform's
fetch_page tool, which routes through the egress proxy that direct sandbox
TLS cannot reach.

Run from the repository root.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

CACHE = Path(__file__).resolve().parents[1] / "data" / "selfhelp" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)

NOW = datetime.now(timezone.utc).isoformat()

# (url_path, title, markdown_content)
PAGES: list[tuple[str, str, str]] = []

def P(path: str, title: str, body: str) -> None:
    url = "https://selfhelp.courts.ca.gov" + (path if path != "/" else "")
    PAGES.append((url, title, body.strip() + "\n"))


# ---- Home ----
P("/", "Self-Help Guide to the California Courts", """
# Self-Help Guide to the California Courts

Resources and information to help you navigate your court case, including step-by-step guides for following procedures and help with understanding your options.

## Get help with papers I was served

Look up by form number to understand your options. (Find the form number in the upper right or upper left corner of your papers.)

Forms you may have been served with include CH-109, CH-100, CH-110 (civil harassment); DISC-001 to DISC-005, DISC-020 (discovery); DV-109, DV-100, DV-110 (domestic violence); EA-109, EA-100, EA-110 (elder/dependent adult abuse); EPO-002 (emergency protective order); FL-100, FL-110, FL-145, FL-200, FL-210, FL-260, FL-280, FL-300, FL-360, FL-600, FL-640, FL-680, FL-683 (family law); GC-210 (guardianship/conservatorship); GV-109, GV-100, GV-110 (gun violence); NC-120 (name change); SC-100, SC-500 (small claims); SUM-100, SUM-130 (summons); SV-109, SV-100, SV-110 (school violence); WV-109, WV-100, WV-110 (workplace violence).

## Start a court case

Find your case type to get started. Case types include: Appeals, CARE Act, Civil harassment restraining order, Conservatorship, Divorce, Domestic Violence Restraining Order, Elder or dependent adult abuse restraining order, Emancipation, Eviction, Gender Recognition, Guardianship, Name Change, Parentage (paternity), Restraining Orders, Small Claims, Stepparent Adoption, Suing someone (civil lawsuit).

## Work on my court case

Take the next step, change an order, see all the options during or after your case. Step 1: choose case type (Ask for a restraining order; Child custody, visitation, and support; Civil harassment restraining order; Civil lawsuit; Divorce; Domestic violence restraining order; Elder abuse restraining order; Eviction; Guardianship; Limited conservatorship; Name Change; Parentage; Small Claims; Stepparent adoption; Traffic ticket); Step 2: choose action.

## Get information about a legal topic

Topics: Appeals, CARE Act, Criminal law, Divorce, Domestic violence, Eviction and housing, Families and children, Gender change, Help for someone with a disability, Immigration, Money and debt, Name change, Restraining orders, Small claims, Suing or being sued, Traffic tickets, Wills, estates, and probate.

## Take care of your traffic ticket

Look up your traffic ticket, ask for a lower fine, go to traffic school, fight your ticket, or pay your fine. Select your county from the 58 California counties.

## Get help from the court

Find self-help centers, forms, interpreters, disability access, and more. Services include: Ask for a Fee Waiver, Ask for an interpreter, Ask for disability accommodation, Find a court form, Find a courthouse, Find your self-help center, Prepare for a remote hearing.

- Find a Free or Low-Cost Lawyer
- Reduce a Traffic Fine (external)
- Search Court Forms (external)
- Learn About Jury Duty (external)

## California Courts of Appeal

- Start your appeal — Don't worry—we'll guide you through every step
- Work on your appeal — Figure out the next step in your case
- Check out resources — Find helpful resources, including a glossary of common terms used in appeals, FAQs, and videos

## Self-Help Locations

Self-Help Centers can provide legal information and resources to people without a lawyer. Help can be in person, over the phone, or online. Enter city, county, or zip code to search.
""")

# ---- Divorce ----
P("/divorce", "The divorce process", """
# The divorce process

Divorce in California takes **at least 6 months** to finish.

There are **4 main steps** in the process. The steps are the same if you are married or in a domestic partnership. Legal separation uses the same steps, but **there is no 6-month waiting period**.

> ⚠️ These steps are not for joint divorce cases. If you are filing one of these cases, go to those pages instead:
> - Joint petition for divorce or legal separation
> - Joint summary dissolution

### Select a step to get instructions and forms

- **Part 1: Start a divorce case** — One spouse (or domestic partner) files papers to start the case and officially lets the other spouse know. Then, the other spouse has a chance to file a response.
- **Part 2: Share financial information** — The spouse that first filed divorce papers must share financial information with their spouse. The other spouse must share their information if they're participating in the divorce process.
- **Part 3: Make decisions** — Make decisions about how to split property and debts, care for your children, and any spousal or child support. You can agree about these things or use a court process to have the court decide.
- **Part 4: Finalize the divorce** — Once all these issues are decided, submit final paperwork to the court and your divorce will become final.

Already know what you are looking for? See All Forms. Index: All Pages.

Video workshops explain the steps in a divorce case: the Dissolution Orientation Workshop and the Declaration of Disclosure Workshop (both from LASCourt).
""")

P("/divorce/start-divorce", "Start a divorce case", """
# Start a divorce case

To start a divorce or legal separation, you must:

1. Fill out and file your court forms
2. Serve your spouse or partner a copy of the filed forms

This page gives you an overview of each step and links to more help.

> ⚠️ Do not follow these steps if you're filing a joint petition for divorce or legal separation or a joint summary dissolution. Visit those pages instead for more information.

To start your case, you'll fill out court forms that ask for basic information like:
- Your name and your spouse's name
- The date you were married or registered your domestic partnership
- If you want a divorce or legal separation
- If you want child custody, support, or property decisions

After you fill them out:
- You file them with the court
- You pay a filing fee, or ask for a fee waiver
- You get copies to serve the other person

You can file in person or by mail. You may also be able to file online.

## Step 2: Serve the other person

Once your forms are filed, you must serve your spouse or partner a copy.

> ⚠️ **You can't serve the papers yourself.** Someone else—like a friend, relative, or process server—must hand them the forms.

This step has strict rules. The court can't move forward with your case until it's done correctly.

## Get help

You can get free help from your court's self-help center. They can help you fill out forms, explain the process, and answer questions.
""")

P("/spousal-support", "Spousal support", """
# Spousal support

Spousal support (also known as **alimony**) is a court ordered payment from one spouse or domestic partner to help cover the other's monthly expenses. In California, when it is between married persons, support is called spousal support. Between registered domestic partners, it's called domestic partner support (or partner support).

**📌 This site uses spousal support to also mean domestic partner support, unless noted.**

A judge can make a spousal support order in a divorce, legal separation, or domestic violence restraining order case.

## Two types of spousal support

**Temporary spousal support:** An order for payments to a spouse before your case is final. You can ask for a temporary support order as soon as you file the case.

**Long-term spousal support:** Support orders made at the end of the case (for example, in a Judgment). These are also called permanent support orders.

Spousal and domestic partner support are difficult legal issues. A lawyer or your court's family law facilitator or self-help center can help you:
- Calculate spousal or domestic partner support
- Figure out how long the support may last and how it may affect your taxes
- Prepare court forms

Related topics: temporary spousal support, long-term spousal support, changing a long-term order, preparing agreements, taxes and spousal support, collecting spousal support, paying spousal support, child support.
""")

# ---- Eviction ----
P("/eviction", "Eviction cases in California", """
# Eviction cases in California

This guide explains the eviction process (called unlawful detainer) for **residential** evictions only. It includes steps for:

- **Landlords**: How to start an eviction case
- **Tenants**: What to do if you get a Notice or court papers

📌 **Note**: This guide is not for commercial evictions (like businesses or stores). Talk to a lawyer if you need help with those.

#### Need help?

Find legal help or housing resources.

## How the eviction process works

This is a basic summary of the steps in a residential eviction case.

1. **The landlord gives notice.** A paper from the landlord that tells the tenant what to do and the deadline. It's not from the court. If the tenant doesn't do what it says, the landlord can start an eviction case. The deadline can be as short as 3 days or as long as 60 or 90 days.
2. **The landlord gives the tenant a written notice.** It says what the tenant must do and the deadline to do it.
3. **The landlord starts a court case.** If the tenant doesn't do what the notice says by the deadline, the landlord can start a court case. This is called an **unlawful detainer** case, and it's how a landlord legally evicts a tenant. The landlord must have someone give the court papers to the tenant. This is called **service**.
4. **The tenant can file a response.** The tenant has a deadline to respond to the court case. If the tenant doesn't respond, the landlord can ask the judge to decide the case without the tenant. If the tenant does respond, either side can ask for a trial if they want one.
5. **The judge makes a decision.** If the landlord wins, the judge gives them a paper (called a **Writ of Possession**) that tells the sheriff to evict the tenant. The sheriff posts a **Notice to Vacate**. This gives the tenant a few days to move out.

> ⚠️ **Important**: A landlord **cannot** lock a tenant out, shut off utilities, or throw out their belongings to make them leave. They must go through the court process. If they do not, they may have to pay the tenant a penalty.

Choose your role: the eviction process for landlords, or the eviction process for tenants.
""")

P("/eviction-landlord", "The eviction process for landlords", """
# The eviction process for landlords

If you want a tenant to move out, you must first tell them in writing. This is called **giving notice**. If they broke a rule in their rental agreement, you must tell them what they did wrong.

If they don't fix the problem or move out, you'll need to ask the court for an order to make them leave.

Evictions can take **30 to 45 days or more**. The time starts when you have court papers delivered to the tenant and ends when they must move out.

### Steps

1. **Give notice.** You must give your tenant a written notice before starting a court case. The type of notice depends on your situation.
2. **Start a court case.** If the tenant doesn't do what you asked in the notice by the deadline, you can file forms in court to start an eviction case.
3. **Ask for court date or default judgment.** If the tenant responds to your case, you can ask for a court date (trial). If they don't respond, you can ask the judge to decide without a court date.
4. **Go to court.** The judge will listen to both sides and then make a decision.
5. **After the judge decides.** If you win, the tenant must move out and may have to pay you. If you lose, the tenant can stay.
""")

P("/eviction-tenant", "The eviction process for tenants", """
# The eviction process for tenants

The eviction process starts when your landlord gives you a written **Notice**. This Notice tells you to do something—like pay rent—or to move out.

If you don't do what the Notice says, your landlord can start a court case to ask a judge to order you to move out. After the landlord gives you the Notice, it can take 30 to 45 days—or longer—for the judge to decide. If you lose the case, the judge can order you to move out of your home.

### Steps

1. **Get a Notice.** Your landlord must give you a written Notice before they can ask a judge to make you move out.
2. **Eviction case starts.** If you don't do what the Notice says, your landlord can file court papers to start an eviction case. You will get a copy of these papers. You must choose what to do: Respond to the court, move out, or do nothing.
3. **Respond to the court.** If you want to have a say in the eviction court case, you must file court papers. There are different ways to respond. The most common is called an Answer. You must file your response papers within 5 days (unlawful detainer is fast). If you don't, the judge can decide the case without hearing from you.
4. **A judge decides.** The judge will look at the case and make a decision. If you filed an Answer, you will have a trial. If you didn't file any type of response, the judge can decide without you.
5. **After a judge decides.** If you lose the case, you can move out, or ask the court for more time to move. If you don't move, your landlord can ask the sheriff to make you move out.
""")

# ---- Small Claims ----
P("/small-claims", "The small claims process", """
# The small claims process

The small claims process is an easier way to take someone to court. It's for when you think the other side owes you less than **$12,500** (or $6,250 if you're suing as a business).

### Steps

- **1. Before you start** — See if small claims is right for your situation.
- **2. Start a small claims case** — Get forms and instructions to start a case, file papers, and serve the other side.
- **3. Go to your court date** — The judge listens to both sides, looks at evidence, and decides who wins or loses the case.
- **4. After the trial** — Find out how to collect money or your options if you owe money.
""")

P("/small-claims/before-you-start", "Check you have a case for small claims", """
# Check you have a case for small claims

Before you start a small claims case, you need to make sure your case is right for small claims court. There are rules about what cases can be decided in small claims court. You can waste a lot of time and energy if you file a case only to find out it can't be decided in small claims.

**IMPORTANT:** As of 10/1/2025, a landlord can no longer sue in Small Claims court for unpaid COVID-19 rental debt above $12,500. COVID-19 rental debt means unpaid rent and other costs incurred before Sept. 30, 2021, due to COVID-19.

## Key questions

- How much money to ask for? In general, an individual can sue for up to $12,500. If you're suing on behalf of your business, you can sue for up to $6,250. You also can sue twice per calendar year for over $2,500.
- Do you only want something other than money? Generally, small claims cases are about money, not for the judge to order someone to do something or not do something.
- You have a legal reason you're owed money. At a hearing, you'll need to be able to tell the judge the reason you are owed money.
- Who to sue and where they are. Sometimes it's clear who owes you money. But sometimes it's not so clear. If the other side is a business, you will need to know their official business name.

Special rules apply if you are suing: an attorney about their fees; the State of California or a local government; a healthcare provider.
""")

P("/small-claims/start-case", "Start a small claims case", """
# Start a small claims case

Here's a simple view of the steps to start a small claims case. The person who starts the case is the plaintiff. The person who is sued is the defendant. The steps can vary a bit depending on your situation. For example, the defendant could sue you back or you could reach an agreement before your court date.

### Plaintiff steps
1. Fill out forms
2. File with court
3. Serve your claim

### Defendant steps
1. Receive claim
2. Prepare for court date
""")

P("/small-claims/trial", "Get ready for your court date", """
# Get ready for your court date

There are some things you can do that will help make you more effective at telling the judge your side of the story at your trial (also called your **court date**). Knowing how to get ready for your court date will also lower your stress.

## Before you start

Sometimes after you serve your small claims papers, the other side will reach out to you to see if you can come up with an agreement without going to court. If you do, you can write up the agreement and ask the court to dismiss your case.

If you don't have an agreement, start to gather your evidence and plan what you're going to say.

### Get any witness or evidence you need

You may need the court to order someone to send information to the court or come to court to talk to the judge about your case. You only need this court order (a **subpoena**) if you can't get the information or the person to come to court voluntarily.

### Ask for court services (if needed)

- Request an interpreter (form INT-300) if you don't speak or understand English very well.
- Request a disability accommodation (form MC-410).

### Watch a small claims case

If you have time, go to court and watch some court hearings. See how the judge talks to the people, what questions they ask, and how much time you may have to give the judge your side of the story.

### Make copies and organize your papers

- Make copies: original for you, copy for the judge, copy for the other side.
- Organize the papers so if the judge asks to see something you can find it easily.

### Plan what you are going to say

- Look over the court form(s) you and the other side filed.
- Think ahead about what the other side might say in court.
- Practice how you'll tell your side of the story.
- Create a list of everything you asked for and why.

### Make arrangements for child care and time off work

You may be in court for 4 or more hours.
""")

P("/small-claims/after-trial", "What happens after your trial", """
# What happens after your trial

After your small claims trial, the judge will either make a decision that day while you're in court or a court clerk will mail the judge's decision to you.

## Read the judge's decision

The judge's decision (called **the judgment**) will be on the Notice of Entry of Judgment (form SC-130 or form SC-200). The judgment will say if the defendant or the plaintiff owe money and how much.

## Figure out if you have next steps

- If the judge decided you aren't owed money, your case is finished. You can't appeal that decision.
- If the judge ordered you to pay the other side and you don't agree you can appeal (challenge the decision). If you don't want to appeal it, then pay the other side right away.
- If the judge ordered that the other side owes you money, you have to wait 30 days from the date the judgment was handed or mailed to you to start to collect the money.

Next steps: Appeal or pay money; Collect money.
""")

# ---- Custody & Support ----
P("/child-custody", "Child custody and parenting time", """
# Child custody and visitation (parenting time)

When you separate from your child's other parent, you need a **parenting plan.** Sometimes parents can agree to a parenting plan. Other times they need the help of the court to come up with a plan.

## What is a parenting plan?

Parenting plans have orders about **child custody** and **visitation**, also called parenting time. Your parenting plan should describe:
- How to care for your children
- Where they will live
- When they will see each parent

Parenting plans must be in the best interest of your children. **Until you have a court order, both parents have the same rights.**

> If you or your child have been abused by the other parent, special laws in domestic violence cases apply to your case.

## Child custody

**Child custody** refers to the rights and responsibilities of the parents for taking care of the children. There are two types:
- **Legal custody**: who makes important decisions for your children (like health care, education, welfare).
- **Physical custody**: who your children live with most of the time.

Legal and physical custody can be shared (joint) or only to one parent (sole).

## Visitation

Types of visitation orders:
- **With a schedule** — often set dates and times.
- **Reasonable** — open-ended; works if parents get along.
- **Supervised** — used when there are concerns about the children's safety.
- **No visitation** — used when visiting would be harmful.

### Virtual visits

Virtual visits are video calls between a parent and child (using Zoom, FaceTime, WhatsApp). They can be used when one parent lives far away or when in-person visits aren't possible.

## Determining what's in the best interest of your child

If you and the other parent can't agree on a parenting plan, then you will have to ask a judge to decide. The judge considers:
- The age and health of the child
- The emotional ties between the parents and the child
- The child's ties to their school, home, and community
- The ability of each parent to care for the child
- Any history of family violence
- Any regular and ongoing substance abuse by either parent

## How to get or change a custody and visitation order

File papers with the court to ask for an order. Different types of cases and papers apply depending on whether you are married, in another family law case, etc.

## How to respond if you got papers

Your options depend on which form you were served: FL-300, DV-100, FL-100, FL-200, FL-260, etc.
""")

P("/child-support", "Child support", """
# Child support

Child support is the amount of money that a court tells a parent to pay every month. This money is to help pay for the children's living expenses.

## Child support basics

By law, both parents must support their children. Sometimes parents can agree on how to share this responsibility without going to court. But if you and the other parent can't agree, you can **ask the court for a child support order**. Usually child support is paid to the person primarily caring for the children.

The duty to pay support typically ends when a child turns 18 and graduates high school (or 19, whichever is first), gets married or enters a domestic partnership, joins the military, is emancipated, or dies. The duty can continue if the child is disabled or if the parents agree.

## How the court calculates child support

Courts use the California "guideline," looking at:
- How much money each parent makes
- How they file taxes
- How much time they spend with the children
- Other factors

There is a free online child support calculator.

## How to get or change a child support order

You can ask for a court order by filing papers in an existing family law case or by starting a new case. The Local Child Support Agency (LCSA) may also be involved. If you have an order and need to change it, you can ask the judge if things changed (like income or time with children). A judge can only change support going back to the day you filed papers.

## How to respond if you got papers

Options depend on which form you were served: FL-300, FL-680/683, DV-100, FL-100, FL-200, FL-260, FL-600. If you do not respond, a judge may make a child support order without your input.

## Where to get free help

The Local Child Support Agency (LCSA) and court self-help centers can provide free assistance.
""")

# ---- Restraining Orders ----
P("/restraining-orders", "Restraining orders", """
# Restraining orders

There are different types of restraining orders. Most restraining orders can order a person to:
- not contact you
- stay away from you

Some types can order someone to move out, protect your children or other family members, and more.

If you need a restraining order, first find out what type you need. Your court's self-help center can help. If someone asked for a restraining order against you, choose the type below to find out your options (the form name will be on your papers).

## Types

- **Domestic violence** (DV-100, DV-109, DV-110): when you are or were in a relationship with someone or are closely related.
- **Civil harassment** (CH-100, CH-109, CH-110): when you are not in a relationship and not closely related (neighbors, coworkers).
- **Elder or dependent adult** (EA-100, EA-109, EA-110): when the person to be protected is 65 or older, or a dependent adult.
- **Workplace violence**: when an employer asks for protection for an employee.
- **Gun violence** (GV-100, GV-109, GV-110): when someone has threatened to harm themselves or others with a gun.
- **School violence**: when a school administrator asks for protection for a student.
- **Emergency and criminal protective orders** (EPO-002): when police ask in an emergency, or judges make the order in a criminal case.
- **Retail crime**: when a business asks for a court order to stop someone from going to a store.
- **Private Postsecondary School Violence** (SV-100, SV-109, SV-110): protection for postsecondary school students.

## Related

- Criminal court
- Victims' rights
- Resources for victims
""")

P("/DV-restraining-order", "Domestic Violence Restraining Orders in California", """
# Domestic violence restraining orders in California

This guide can help you follow the process to ask for a restraining order, ask to change, end, or renew a restraining order, or know what you must do if you received restraining order papers.

If you are in danger right now, call 911 or seek safety. Websites you visit may be seen by someone else later; always clear your browsing history.

## Overview

A **domestic violence restraining order** is against someone you've dated or had an intimate relationship with (including a spouse or domestic partner), or a relative if they are your child, parent, sibling or grandparent (including in-laws).

It can be granted against someone who has abused you or your children. Abuse can be emotional, psychological, verbal, or physical; can take place anywhere, including online; and can include stopping you from accessing money or basic needs, or isolating you from friends or family.

If you are 12 or older, you can ask for a restraining order on your own without your parent's permission.

## What can a restraining order do?

A judge can grant a restraining order to protect someone, their children, their property, or their pets. Orders can include:
- No contact
- Not harass, stalk, threaten or harm
- Stay away by a certain distance
- Move out from a shared home
- Not have guns, firearms, ammunition, or body armor
- Pay spousal support (if married)
- Pay child support (if you have children together)
- Child custody orders

There is no court fee to file for a domestic violence restraining order.

## Temporary protection

If you need protection right away, a judge can make a decision quickly on whether to give you a temporary restraining order (TRO), usually the same day or next business day.

## If someone asked for a restraining order against you

Read the papers carefully:
- Form DV-110 means the judge granted a temporary restraining order against you. You must follow all orders.
- Form DV-109 has your court date. Make sure to go if you don't agree to the order.
""")

P("/CH-restraining-order", "Civil Harassment Restraining Orders in California", """
# Civil Harassment Restraining Orders in California

A **civil harassment restraining order** is against someone you are **not** closely related to and have **not** had an intimate relationship with—such as a neighbor, landlord, co-worker, or more distant relative (aunt/uncle, niece/nephew).

It can be granted against someone who has harassed, threatened, harmed, or stalked you (including online).

## What can it do?

- No contact
- Not harass, stalk, threaten, or harm protected people
- Stay away by a certain distance
- Not own or have firearms, ammunition, or body armor

## Temporary protection

A judge can grant a temporary restraining order (TRO) the same day or next business day.

## If someone asked for an order against you

- Form CH-110 means a temporary order was granted — you must follow all orders.
- Form CH-109 lists your court date. Go if you don't agree. At the hearing, the judge will decide whether to grant an order lasting up to 5 years.

There is a filing fee for civil harassment restraining orders (unless you qualify for a fee waiver).
""")

P("/EA-restraining-order", "Elder or Dependent Adult Abuse Restraining Orders in California", """
# Elder or Dependent Adult Abuse Restraining Orders in California

The court can grant a restraining order to stop someone who is abusing or neglecting an **elderly person or a dependent adult**.

Abuse can be emotional, physical, or financial; can happen anywhere (including online); and can include stopping someone from accessing money or basic needs, isolating them, or depriving them of food or medicine.

## Who can ask?

- Someone who is **65 or older** or a **dependent adult** (18-64 with mental/physical limitations) can ask for themselves.
- Others can ask on their behalf: conservator, trustee, attorney, guardian ad litem, or county Adult Protective Services.

## What can it do?

- No contact; stay a certain distance away; move out (if they live with the protected person)
- Get counseling or anger management classes
- No firearms, ammunition, or body armor

There is no court fee to file for an elder/dependent adult abuse restraining order, or to respond to one.

## If you received papers

- Form EA-110 means a TRO was granted; you must follow all orders.
- Form EA-109 lists your court date.
""")

P("/civil-harassment-restraining-order", "Civil harassment restraining order", """
# Civil harassment restraining order

See the Civil Harassment Restraining Orders page (/CH-restraining-order) for full details. This alias route redirects users to the CH- code pages.
""")

# ---- Other family / person-topics ----
P("/guardianship", "Probate guardianships in California", """
# Probate guardianships in California

This guide can help you understand what a guardian does, become a probate guardian, respond if someone started a court case to become your child's guardian, end a guardianship, or ask for visitation rights as a parent in a guardianship.

Other sections cover guardianships in juvenile dependency court or for older immigrant youth (ages 18-20) seeking special immigrant juvenile status.

## What is a guardianship?

A guardianship is when an adult who is not a child's parent is legally responsible for the child's care because the parent is unable to care for them. It may also mean someone manages the child's money or property.

### Two types

**Guardianship of the person:** the guardian has the right to make legal decisions about the child's life (medical care, school) and provides housing, food, clothing, safety.

**Guardianship of the estate:** someone manages the child's finances (needed if the child has substantial money, income, or property). Fiduciary duties apply; a lawyer is usually recommended.

Guardianships differ from adoption: parents' rights are only suspended, not permanently ended, and the court stays involved.

### Why is a guardianship needed?

Reasons include parental illness, substance abuse treatment, military deployment, incarceration, or a history of abuse. Other options (like a power of attorney for school/medical decisions) may be less restrictive.

## How to become a guardian

1. **File papers with the court** ($225 for guardianship of the person; $450 for estate; fee waivers available based on the child's income).
2. **Let the child's family members know** (serve papers properly).
3. **Talk to an investigator and go to court.** The court appoints someone to investigate, then the judge holds a hearing.

As a guardian you will need to send annual updates to the court and return for related issues (visitation, moving, termination).
""")

P("/parentage", "Parentage in California", """
# Parentage in California

In California, only legal parents can get custody and visitation (parenting time) orders about their child. Legal parents also have a responsibility to support their child financially.

## Who is a legal parent?

- You are the child's birth parent (not a surrogate)
- You and the other parent were married or registered domestic partners when the child was born or conceived
- You and the other parent filed a Declaration establishing you as legal parents
- A judge determined that you are a legal parent

Assisted reproduction and surrogacy cases may require additional steps.

## Why legal parentage matters

Legal parents can ask for custody and visitation orders; are required to financially support their child; can be listed on the birth certificate; and the child can inherit and get financial benefits (Social Security, survivor benefits) from them.

## Different ways to determine parentage

1. **Sign a voluntary declaration (VDOP):** both parents sign form VDOP and file it with the state; once filed it has the same effect as a court order.
2. **Ask the court to determine parentage:** a judge decides; local child support agencies can also open a case.
3. Genetic testing may be ordered.

A child can have more than 2 legal parents in limited cases.

## If you received court papers

- Form FL-200/Summons FL-210: someone is asking the judge to determine parentage.
- Form FL-600: Local Child Support Agency (LCSA) filed papers; they may be asking for a child support order and/or a parentage determination.

Every county has a Self-Help Center (Family Law Facilitator) for free help.
""")

P("/name-change", "Change your name in California", """
# Change your name in California

You can legally change your name by filing papers in court. If a judge agrees, they will give you a court order that states your new legal name. You need this order to change your name on identity documents, like your driver's license, passport, or social security card.

## Basic steps

1. **File forms with the court.** Filing fee $435-$450; fee waivers available. Clerk gives you a hearing date.
2. **Publish your forms in a newspaper** for one month (legal notice section). Fee applies.
   - ⚠️ Publication is NOT required if your name change is to match your gender identity or is filed with a gender change recognition request.
3. **For child name changes,** the other parent may need to be served with a copy.
4. **A judge will decide in about 2 to 3 months.**

Other paths: name change through marriage license, as part of a divorce, or as part of naturalization (U.S. citizen).

Out-of-state residents can change California-issued records (birth/marriage certificate), but must follow specific differences (like county filed).

A name change will not change who a child's legal parent is — that requires a parentage case.
""")

P("/gender-recognition", "Court order to recognize change of gender in California", """
# Court order to recognize change of gender in California

In California, you can ask the court for an order recognizing your or your child's gender change. You can request a gender marker of female, male, or nonbinary. The process takes about two months.

## Do you always need a court order?

You do **not** need a court order to update: California birth certificate, California marriage certificate (if spouse agrees), or California driver's license. Out-of-state birth certificates and federal identity documents may require a court order. You **do** need a court order to change your name; you can combine this with a gender recognition request.

## Basic steps

1. File forms (fee $435-$450; fee waiver available).
2. For a child's gender change, serve the other parent(s).
3. Judge decides in 1-2 months.

📌 **You do not need to provide any medical documentation** to get a court order recognizing gender change, or to change California-issued documents. You don't need to have undergone any gender-affirming care.

Out-of-state residents can change California-issued records but must observe specific filing differences.
""")

P("/emancipation", "Emancipation in California", """
# Emancipation in California

Emancipation is a legal way for a 14- to 17-year-old to become free from their parent's custody and control. In many ways they are legally like an adult.

## What emancipation means

- You are free from custody and control of your parents/guardians: you can live where you want, apply for a work permit, keep your earnings, get a credit card, and sign up for school without permission.
- Your parents are no longer required to support you; you are responsible for your bills and can be sued.
- You are not a full adult: you must still go to school, need parental permission to marry, cannot vote until 18, and cannot drink until 21.

## Three ways to become emancipated

1. Get legally married (with parent and court permission).
2. Join the military (with parent and military permission).
3. Get a court order (Declaration of Emancipation). You must prove you are at least 14, not living with parents (parents don't mind), can handle your own money and pay your bills, have a legal way to make money, and emancipation is good for you.

Having a baby does not automatically emancipate you. Other options (counseling, living with another adult, public agency help) may be preferable.
""")

P("/stepparent-adoption", "Stepparent adoption in California", """
# Stepparent adoption in California

A stepparent can adopt the child of their spouse or domestic partner through the stepparent adoption process. Adoption gives the stepparent permanent legal parent rights and responsibilities.

## Consent from the other parent

The court will end the parental rights of the child's non-custodial (other) parent. The process generally requires the other parent's written consent. In some cases, the other parent can retain parental rights (three legal parents).

If the other parent doesn't agree or refuses, their status (presumed parent vs. alleged father) determines what process you follow. Some situations do not require consent: the other parent has died; signed a waiver; signed a denial of paternity; their whereabouts are unknown after diligent search; or their identity is unknown.

## Steps

1. Contact the child's other parent.
2. Depending on their response, follow the appropriate path (consent, termination of rights, etc.).
3. File forms, attend the court hearing, get the adoption order.

If the child's stepparent asks you for consent to adopt, you have options whether you agree or disagree.
""")

# ---- Other topics ----
P("/wills-estates-probate", "Guide to wills, estates, and probate court", """
# Guide to wills, estates, and probate court

This Guide has information to help you create the legal documents you or a loved one may need to have a plan if you become sick, and information about what happens to someone's property (the estate) after they die.

Choose a topic:
- **Wills, estates, and advance care planning** — basic information and sample legal documents (will, power of attorney) to have a plan.
- **Property after someone dies** — transferring property with or without going through probate court.
""")

P("/helping-person-impairment-or-disability", "Helping a person with an impairment or disability", """
# Helping a person with an impairment or disability

This guide covers definitions (function, impairment, disability), options to help someone, general and limited conservatorships, and step-by-step guidance for limited conservatorships.

There is a range of options to help someone who has trouble providing for personal needs, managing money, or making decisions. Most don't require court appointment. A **conservatorship** is court-appointed authority for another person to act or make decisions.

You must explore all less-restrictive options before going to court (judges will require this). Parents of children nearing 18 with developmental disabilities have transition options.

Next: Explore other options (Supported Decision Making, Power of Attorney); find places to get support; find out about conservatorships.
""")

P("/conservatorship-index", "Conservatorship index", """
# Conservatorship index

Find a specific page in our guide to helping someone with an impairment or disability, or view step-by-step instruction on limited conservatorships.

## Guide to helping a person with an impairment or disability
- Introduction; Options to help someone; Helping a young adult with a developmental disability; Introduction to conservatorships.
- Support resources; legal and social service resources.

## Limited conservatorships
- Introduction; Rights of a limited conservatee; Responsibilities/duties of limited conservator; Limited conservatorships of the estate.
- Fee waivers in a conservatorship.
- Case overview: gather information; fill out forms; file forms; notify person/family/others (service in person, service by mail); investigation and reports; prepare for court; go to court date.

## Moving with a conservatee
- Within California; out-of-state (with court date prep).

## If the conservatee dies
- What to do.
""")

P("/debt-lawsuits", "Debt lawsuits in California", """
# Debt lawsuits in California

When a company (creditor or debt collector) claims you didn't pay back a debt, they can file a lawsuit against you in court. This guide covers options if you are sued, and things you can do to avoid a lawsuit.

## You may be able to take action before getting sued

Negotiating with the creditor to settle a debt before a lawsuit is filed is often the least expensive way to resolve it. California laws limit what creditors can do when contacting you.

## If you're being sued, you'll receive official court papers

At least a **Summons** and **Complaint**, usually served in person or left with someone 18+ at your home/work/mailing address.

Select the type of debt for specific guidance:
- Credit Card Debt
- Student Loan Debt
- Auto Loan Debt
- Medical Debt
- Other type of debt
""")

P("/discovery-civil", "Discovery in civil cases", """
# Discovery in civil cases

**Discovery** allows you to get information and evidence from the other party or other persons you can use in your lawsuit.

If you're the plaintiff you must prove your case by stronger evidence than the other side. If you're the defendant you must raise enough doubt about the plaintiff's case. Discovery is how you gather evidence.

## Request from the other side

Follow court rules and ask in writing using specific formats. Some types are easier (form interrogatories, requests for admission); others like depositions are complex and expensive (consider hiring a lawyer). Other types include requests for physical/medical/psychiatric examinations.

## Request from non-parties

Use a **subpoena** to require individuals or companies who aren't part of the case to produce documents or business records, or to testify.

## You may receive discovery requests

If you do, you have specific deadlines and requirements for responding. Objections must be made properly; inadequate responses can lead to motions to compel or sanctions.

Topics: written discovery from a party; discovery from a non-party (subpoenas); responding to discovery requests.
""")

P("/criminal-court", "Guide to criminal court in California", """
# Guide to criminal court in California

Covers an overview of the criminal court process, how to clean a criminal record (expungement), and victims' rights/restitution.

Only the government (District Attorney's Office) can file criminal charges. The person accused is the defendant, presumed innocent until proven guilty beyond a reasonable doubt.

## Three types of charges

- **Infractions:** least serious (speeding tickets etc.); no jail time, fine only; no right to appointed lawyer or jury. Handled primarily in traffic court.
- **Misdemeanors:** up to 6 months to a year county jail; probation/fines possible; right to appointed lawyer and jury trial.
- **Felonies:** state prison, possibly life; other penalties possible; right to appointed lawyer and jury trial.

> If you are facing felony or misdemeanor charges, talk to a lawyer. If you cannot afford one, tell the judge at your arraignment — the court will appoint a public defender.
""")

P("/criminal-law", "Criminal law", """
# Criminal law

Criminal court topics:
- **Criminal court** — Overview of the criminal court process.
- **Clean your record** — Reduce the impact of your California criminal record.
- **Victims' rights** — Victims' rights before, during, and after a criminal case.
- **More topics** — All topics in the criminal court section.

Related topics: Juvenile justice, Traffic, Protective orders.
""")

P("/appeals", "Appealing your case in the Court of Appeal", """
# Appealing your case in the Court of Appeal

An appeal is when someone who loses a case in a trial court asks a higher court (the appellate court) to review the trial court's decision. Appealing is very hard; talk to a lawyer to help you.

This page is for cases in the **Court of Appeal**. Cases in the appellate division of superior court are handled at that court.

- **Which court do I appeal in?** Figure out if Court of Appeal or appellate division.
- **Step-by-step instructions** for the appeal process.
- **Options other than appealing.**
- **Helpful resources**, including a glossary, FAQs, and forms list.
""")

# ---- Court services ----
P("/fee-waiver", "Ask for a Fee Waiver", """
# Ask for a fee waiver if you can't afford court fees

In most cases you must pay a fee to file papers with the court. If you can't afford court fees you can ask for a **fee waiver**. A fee waiver lets you file for free and may cover other court costs.

## What a fee waiver covers

- Filing fees
- Fees to respond to a case
- Copies of court papers (including certified copies)
- Sheriff service fees
- Court reporter fees for trial attendance
- Other fees listed on form FW-003 item 4

## What it doesn't cover

- Court reporter transcripts (may be partially reimbursable via the Transcript Reimbursement Fund)
- Fees later assessed if your financial situation improves or you recover money (you'll get notice and a chance to be heard)
- Other fees not covered (use form FW-002 for additional waivers)
- Lawyer fees, private mediation, fines/penalties

Your fee waiver request information is confidential — only the court sees it.

## When to ask

When you first file papers and have to pay a filing fee; you can also ask later if finances change. Filing fees shown are estimates; check with your county.

In divorce/legal separation/annulment cases, the fee waiver can cover filing, responding, and request-for-order fees, but doesn't decide monetary issues between spouses. A fee waiver expires 60 days after judgment/dismissal/final decision.

## Who qualifies (meet ONE of three)

1. You receive public benefits (Unemployment, Medi-Cal, CalFresh, WIC, CalWORKs, General Assistance, SSI/SSP, Tribal TANF, IHSS, CAPI).
2. Your household income is below set amounts listed on form FW-001.
3. You can't meet basic needs AND pay court filing fees.

Different rules apply for guardianship/conservatorship fee waivers and appeal/writ fee waivers.

## How to ask

Gather the information you need (pay stubs, bills, bank statements — don't turn these in; use for reference). Fill out Request to Waive Court Fees (form FW-001) and item 1 on Order on Court Fee Waiver (form FW-003). Turn them in with the papers you're filing. The clerk will review; if granted your fees are waived. If denied you have 10 days to pay or ask for a hearing.
""")

P("/getting-legal-help", "Getting legal help", """
# Getting legal help

There are many ways to find legal help. This guide covers free or low-cost legal help, and how to hire and work with a lawyer.

- **Get free or low-cost legal help** — a number of resources including court self-help centers, legal aid organizations, lawyer referral services, and law libraries.
- **Hire a lawyer** — you can successfully represent yourself in many cases, but law can be complicated; tips on finding, interviewing, and working with a lawyer.
""")

P("/tips-your-day-court", "Tips for your day in court", """
# Tips for your day in court

Get more tips if you have a remote hearing (by computer or phone).

## Before you go

- Know where you're going and how long it takes; plan to arrive early.
- If you're late you may miss your turn. Note the courtroom clerk's phone number.
- Dress nicely (job-interview style); avoid shorts, hats, flip flops.
- Arrange childcare (courthouses may have Children's Waiting Rooms).
- Gather what you need: pen/paper, folder with your papers, the other side's papers, three sets of anything for the judge to review, notes of what to say.
- If you're ill or have car trouble, call the clerk and the other side.
- It can help to watch court proceedings the week before.

## In the courtroom

- Wait in the public area until your case is called.
- Petitioner/plaintiff typically sits at the right table; respondent/defendant at the left (varies by court).
- Follow courtroom rules: no food/drinks; phones off; no hats/sunglasses; don't interrupt; refer to judge as "your honor" or Judge; stop talking if the judge interrupts.
""")

# ---- Serve / Service / Discovery supporting pages ----
P("/subpoena", "Subpoena", """
# Subpoena

A **subpoena** is a court order that requires a person to:
- come to court to testify as a witness,
- bring records or documents to a court hearing or trial, or
- produce documents for copying.

Subpoenas are commonly used in civil, family, and criminal cases to get information from people or organizations that aren't a party to the case. Parties can be required to produce documents through other discovery procedures (like a Request for Production) without a subpoena.
""")

P("/domestic-violence-child-custody", "Domestic violence and child custody", """
# Domestic violence and child custody

If you or your child have been abused by the other parent, special laws apply. A judge must consider a history of domestic violence when making custody and visitation decisions. A parent convicted of certain offenses may not receive custody unless the court finds it's in the child's best interest and specific conditions are met.

A domestic violence restraining order can include temporary custody and visitation orders. The court must apply a **rebuttable presumption** that a parent who has committed domestic violence should not get sole or joint custody. Supervised visitation may be ordered.
""")

# ---- Traffic ----
P("/traffic", "Traffic tickets in California", """
# Traffic tickets in California

**Scam alert:** The court will never text, call, or email you to ask for payment. Don't click links or give personal info.

If you get a traffic ticket in California you can:
- Pay the ticket (including traffic school)
- Fix any issues in a fix-it ticket
- Ask the court for a trial if you don't agree with the ticket

This page covers infraction traffic tickets only; NOT parking tickets (handled by the issuing agency), and NOT DUI tickets (criminal court).

## What is a traffic ticket?

A police officer gives you a traffic ticket when they believe you broke a traffic law. Your ticket says what law you allegedly broke, which court is handling the case, what to do and by when. You'll get a reminder/courtesy notice in ~30 days with bail amount, due date, and options including traffic school eligibility.

## Option 1: Pay the ticket

Paying means you admit (or don't contest) the charge — conviction/forfeiture of bail. Some tickets add a DMV point and may raise your car insurance, but traffic school may prevent that. Pay online, by mail, or in person at your county court. If you can't afford to pay, you can ask for more time, a lower fine, a payment plan, or community service.

Pleading guilty vs. no contest: same result for the ticket, but a guilty plea can be used against you in a later civil suit, while no contest generally cannot.

## Option 2: Fix any issues (fix-it ticket)

For correctable violations (broken tail light, expired registration, proof of insurance correction), fix the problem, get a Certificate of Correction signed, send it with a small fee to the court.

## Option 3: Ask for a trial

Pleading not guilty. You can ask for traffic school or a lower fine even at trial — judge decides.

Two trial types:
- **In-person trial:** You and the officer appear; judge decides. You don't have to pay bail first.
- **Trial by written declaration:** You and the officer submit written statements; judge decides by reviewing them. You usually must pay bail first (refunded if found not guilty). Some courts allow MyCitations tool without prepaying bail.

## Points and insurance

A conviction adds DMV points. Too many points leads to license suspension. Points affect your car insurance rates. Traffic school can mask a point from insurance.

## If you do nothing

You may be charged additional fees, your case could be referred to collections, your license may be suspended, or a hold may be placed (civil assessment).
""")

# ---- Save ----
def main() -> None:
    index_lines = []
    for url, title, body in PAGES:
        from urllib.parse import urlsplit
        path = urlsplit(url).path or "/"
        slug = slug_from_url(url)
        fname = f"{slug}.md"
        (CACHE / fname).write_text(body, encoding="utf-8")
        index_lines.append(json.dumps({
            "url": url,
            "title": title,
            "file": fname,
            "fetched_at": NOW,
            "status": 200,
            "lang": "en",
        }))

    (CACHE / "_index.jsonl").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    print(f"seeded {len(PAGES)} pages into {CACHE}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from selfhelp.parse_page import slug_from_url  # type: ignore
    main()
