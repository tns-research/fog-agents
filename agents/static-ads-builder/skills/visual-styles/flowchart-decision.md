---
slug: flowchart-decision
name: Flowchart Decision Tree
funnel_fit: TOFU, MOFU
---

# Flowchart Decision Tree

## Description

A static designed as a simple visual logic tree, 2-4 yes/no questions that guide the viewer toward the inevitable conclusion that they need the product. The format is "interactive" in a static frame: the viewer mentally follows the path, making micro-decisions that lead to the product. The engagement is earned through participation, once someone starts following a flowchart, they want to reach the end.

## Performance signal

"It's kinda interactive. Once people start reading, they want to follow it to the end" (Magritte/20K-ad analysis, Miracle, Coterie Baby, Paula's Choice examples). The flowchart format taps into the brain's completion bias and decision-making pathways. It's an "under the radar" format, rarely used, but with high engagement when executed clearly. The format's novelty in paid social gives it strong pattern-interrupt value.

## Funnel fit

- **TOFU:** Valid when the entry question is universally relatable ("Votre peau est-elle vraiment hydratée?"). The flowchart becomes a self-diagnosis tool, the viewer learns they have a problem they didn't know about.
- **MOFU:** Primary fit. The flowchart guides warm audiences through a decision process that confirms the product is right for them. Each question resolves an objection or validates a need.
- **BOFU:** Avoid. The game-like format is too playful for conversion. BOFU needs directness.

## Visual recipe

- **Format + crop:** Vertical 4:5 (feed). 9:16 for Stories (more space for the tree). Avoid 1:1, the tree needs height.
- **Camera position:** N/A, this is a pure graphic/typography format.
- **Focal length:** N/A.
- **Lighting:** N/A.
- **Color grade:** Clean, bright, graphic. Branch paths in distinct colors.
- **Environment:** Clean solid-color background. The flowchart IS the visual.
- **Composition logic:**
  - **Entry question at top**: large, bold, centered. This is the hook.
  - **Branching paths flow downward.** Each question node is a rounded rectangle or circle with a short yes/no question (3-8 words).
  - **Answer branches:** "Oui" and "Non" arrows leading to the next node. Paths converge toward the product at the bottom.
  - **All paths lead to the product.** This is the key structural trick, whether the viewer answers yes or no at each branch, the conclusion is the same: they need the product. The "no" paths reach the product through a different logical route.
  - **Product at the bottom**: the conclusion node. Product image with a short resolution statement ("Vous avez besoin du Gel Originel").
  - **2-4 question nodes maximum.** More creates tiny text and visual chaos.
  - **Connector arrows** are clean, thin, with clear direction. "Oui" and "Non" labels on the arrows.
- **Subject:** No human subject. Pure graphic design.
- **Exclusions:** No more than 4 nodes. No dead-end paths (every path must reach the product). No tiny text, every node must be readable at mobile scale. No complex branching, keep it a simple tree, not a network graph.

## image_prompt_snippet

```
Vertical 4:5, flowchart decision tree composition. Clean [BACKGROUND COLOR: white / cream / light brand color] background. TOP: entry question in large bold [TEXT COLOR] sans-serif inside a [rounded rectangle / circle] node: "[ENTRY QUESTION, universally relatable, 4-10 words]". Two arrows descending: left arrow labeled "Oui" in [green / brand color], right arrow labeled "Non" in [red / grey]. Each leads to a [NODE 2 question, 3-8 words] inside a smaller node. Further branching with "Oui"/"Non" arrows. [2-4 total question nodes.] All paths converge to a CONCLUSION NODE at the bottom: use the attached product reference image ([BRAND], [PRODUCT NAME]) as the single source, small product image inside or beside the conclusion node with text "[CONCLUSION, e.g. Vous avez besoin du Gel Originel]" in bold [BRAND COLOR]. Arrows: thin, clean, with clear directional flow. Nodes: consistent style (same shape, same border color, consistent sizing). Layout: organized top-to-bottom, symmetric branches. No dead-end paths. No more than 4 question nodes. Every node readable at mobile thumbnail scale. (Style ref: Paula's Choice, Miracle, interactive logic, completion bias, inevitable conclusion)
```

## Typography notes

- **Entry question** is the largest text, it's the hook. Bold, centered, inside the entry node.
- **Branch questions** are medium-weight, inside smaller nodes. Consistent font and size across all nodes.
- **"Oui" / "Non" labels** on arrows are small, color-coded (green/red or brand accent/grey).
- **Conclusion text** is bold, alongside or below the product. It confirms what the flowchart has proven.
- **Font style:** Geometric sans-serif throughout. Bold for entry question, medium for branch questions, bold for conclusion.
- **No `headline` in the traditional sense**: the entry question IS the headline. The `headline` field in the brief JSON contains the entry question.

## Constraints

- **2-4 question nodes only.** More is unreadable at mobile scale. Fewer doesn't feel like a flowchart.
- **All paths must reach the product.** No dead ends. The structural joke of the format is that the conclusion is inevitable, every path leads to "you need this product."
- **Questions must be simple yes/no.** No open-ended questions. No multi-choice. Binary decisions keep the format clean and fast.
- **Each question is 3-10 words.** No long sentences inside nodes.
- **The entry question must be universally relatable.** It should make the viewer think "hmm, let me check", triggering the first micro-engagement.
- **Apply sparingly**: 1 per batch. The format is novel but loses its charm when repeated.

## Example use

TOFU brief for NaturAloé Gel Originel: Entry node: "Votre peau est-elle vraiment hydratée?" → Oui: "Sans tiraillements à midi?" → Non → conclusion. Non: "Vous utilisez un gel d'aloé vera?" → Oui: "Il contient plus de 50% d'aloé?" → Non → conclusion. All paths converge to: product image + "Passez au Gel Originel, 94% d'aloé vera pur."
