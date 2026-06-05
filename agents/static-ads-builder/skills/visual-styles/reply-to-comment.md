---
slug: reply-to-comment
name: Reply-to-Comment Native
funnel_fit: MOFU, BOFU
---

# Reply-to-Comment Native

## Description

A static designed to look like a native Instagram or Facebook comment thread, a user's question or objection at the top, followed by a brand reply that naturally spotlights the product. The format mimics organic social interaction, disarming the viewer's ad-detection filter. It feels like eavesdropping on a real conversation, not being sold to. The question is the hook; the answer is the sell.

## Performance signal

"The reply to comment format is another native way to address common questions your prospects might have" (Backlinko, Huel example). The AMA/Q&A format from the 20K-ad analysis (Arrae, Solawave, Lemme) follows the same principle, "It feels like a real person answering real questions, not a brand selling." Native-format statics consistently outperform polished branded creatives because they bypass the brain's ad-detection: "If your first 3 seconds look like an ad, you've already lost."

## Funnel fit

- **TOFU:** Light use. Works when the question is universally relatable ("C'est quoi la différence entre un gel d'aloé vera bio et un gel en pharmacie?"). The question itself must be the scroll-stop hook.
- **MOFU:** Primary fit. Warm audiences have specific questions and objections. This format answers them in a trust-building way, the question validates their concern, the answer resolves it.
- **BOFU:** Strong fit. For audiences near conversion, this format handles the final objection: "Est-ce que ça vaut vraiment le prix?" → answer with value proof.

## Visual recipe

- **Format + crop:** Vertical 4:5 (feed). 9:16 for Stories. Square 1:1 acceptable.
- **Camera position:** N/A for the comment UI. Product photo (if included) is frontal, lo-fi, casual.
- **Focal length:** 28mm (phone camera) for any product photo element, maintains the native feel.
- **Lighting:** Natural, casual. If product appears, it should be in a real context (hand-held, on a counter), not studio-lit.
- **Color grade:** Neutral, ungraded, native platform UI colors (white background, dark grey text, blue/grey interface elements).
- **Environment:** The "environment" is the platform UI itself, a white card with comment thread styling. If a product photo is included, it sits within the reply as an inline image.
- **Composition logic:**
  - **Top section:** User comment styled as a native Instagram/Facebook comment, avatar circle (generic or blurred), username, and the question/objection text. The comment should feel real: informal language, natural phrasing, maybe a typo or emoji.
  - **Reply section:** Brand reply below. Brand avatar/logo, brand username, reply text that naturally addresses the question while spotlighting the product. The tone is conversational, helpful, not salesy.
  - **Product element (optional):** A small product photo inline with the reply, or the product held casually in a photo attached to the reply. Lo-fi, not studio.
  - The entire composition should be indistinguishable from a real comment thread at first glance.
- **Subject:** No traditional subject. The "characters" are the commenter and the brand. Product optional.
- **Exclusions:** No studio photography. No polished brand voice in the reply (keep it conversational). No obviously fake usernames or avatars. No long replies (3-4 sentences max). No hard sell language ("BUY NOW", "LIMITED OFFER"), the format's power is in its subtlety.

## image_prompt_snippet

```
Vertical 4:5, native social media comment thread composition. White background mimicking [Instagram / Facebook] comment UI. TOP: user comment, small grey avatar circle, username "[USERNAME, natural, not obviously fake]", comment text in dark grey regular-weight sans-serif: "[USER QUESTION/OBJECTION, informal, natural phrasing, 1-2 sentences]". Below: thin grey separator line. REPLY: brand avatar (small circle with [BRAND] logo or initial), brand username "[BRAND handle]", reply text in dark grey sans-serif: "[BRAND REPLY, conversational, helpful, 2-4 sentences, naturally mentions product benefit without hard sell]". [OPTIONAL: small product photo inline, use the attached product reference image ([BRAND], [PRODUCT NAME]) as the single source, rendered as if it were a phone photo attached to the comment, casual angle, natural lighting.] Platform UI elements: subtle like/reply icons in light grey below each comment. Overall: native, casual, indistinguishable from a real comment thread at first glance. No studio lighting. No polished graphics. No hard sell language. (Style ref: Huel reply-to-comment, Arrae AMA, native, trust-building, conversational)
```

## Typography notes

- **All text mimics platform native fonts.** Regular-weight sans-serif (approximating Instagram/Facebook system font). No bold, no custom fonts, no brand typography, the point is to look native.
- **Username** is slightly bolder or in a different color than the comment text (matching platform convention).
- **UI elements** (like/reply icons, timestamps) are rendered in light grey, present for authenticity but not attention-grabbing.
- **No headline or subheadline in the traditional sense.** The user's question IS the headline. The brand's reply IS the subheadline.
- **The `headline` field in the brief JSON** should contain the user's question (for reference/copy tracking). The `subheadline` field should contain the core of the brand reply.

## Constraints

- **The question must be real or plausible.** Use actual customer comments, DMs, or FAQ questions. Fabricated questions that no one would ask break the format's authenticity.
- **The reply must be conversational.** No marketing jargon, no exclamation marks, no "Act now!" The tone is a knowledgeable friend answering a genuine question.
- **3-4 sentences maximum for the reply.** Longer replies lose the native feel, real comment replies are short.
- **Platform UI must be accurate.** Incorrect interface elements (wrong icon shapes, wrong spacing) break the illusion instantly.
- **No hard sell.** The product mention must be natural and helpful, not forced. The viewer should feel they learned something, not that they were pitched.

## Example use

MOFU brief for NaturAloé Gel Originel: White background, Instagram comment UI. User: "@marie_klr" asks "C'est quoi la différence avec les gels qu'on trouve en pharmacie ? C'est juste du marketing ?" Brand reply: "@naturaloe_officiel" responds "Pas du tout 😊 La plupart des gels en pharmacie sont reconstitués à partir de poudre d'aloé. Le nôtre est un gel natif pressé à froid, 94% de pulpe fraîche. Tu sens la différence dès la première application, il pénètre sans coller." Small product photo inline.
