# Team kickoff meeting: SIH 2026, FinTech / InsurTech (7 Nov 2026)

- Recording: /Users/dewa/Downloads/51 Niven Rd 14.m4a (42 min 41 s)
- Transcribed and diarized by Hermes (Grok, xAI speech-to-text with speaker labels). Speaker names were mapped by Claude from the self-introductions.
- People: Devnavin Madeswaran ("Dev"), Dewa, Deval Gupta, Bhoomi Agrawal, Rafael, Akash Singh ("Sky").
- **Better source for who said what:** the Google Meet transcript in /Users/dewa/Documents/Projects/SIH/sih-fin-4/docs/resources/meet-notes-2026-11-07-gemini.md. It has correct speaker names from the Meet accounts. This file (Hermes) is a second, independent transcript. Use it to check wording. Its speaker labels are less reliable.

## Summary

### Who is who (from the introductions)

| Person | Background | What they offered |
|---|---|---|
| Devnavin (Dev) | SMU, same entrepreneurship class as Dewa. Licensed financial adviser (Financial Alliance), runs his own practice for Indian expats. Income is one of his general-insurance partners. "Non-tech guy." | Insurance domain knowledge. Will send sample policy documents (cyber insurance and other general insurance). Has SME clients in Singapore and can test the idea with them. |
| Dewa | SMU, Information Systems Y2. About 10 hackathons, 5 school-level wins. Building a budgeting app (screenshot input) on the App Store and Play Store. | Technical build. Has Claude Max, a DeepSeek API key and a Grok subscription. |
| Rafael | Singapore Polytechnic. Won NUS Hack for Good and Singapore Poly entrepreneurship hackathons. Tech product manager experience at Prudential. | Research, product thinking, prototyping. Shared his research notes on screen. |
| Akash | Same Indian university and student open-source club as Deval and Bhoomi. About 7 hackathons. Graduated 7 to 8 months ago, works at a US startup on infra, DevOps, MLOps, some fintech. Currently in Brooklyn, New York. | Fast prototyping, leadership, presentations, stage speaking. Flies US to Bangalore to Singapore. |
| Deval Gupta | ML engineer at a startup, also iOS and Android development. Cybersecurity. About 5 hackathons including Smart India Hackathon. | ML and data. Will set up a Notion page for the decisions. |
| Bhoomi | Student in Bangalore. AI engineer background, automation. Smart India Hackathon winner (2024, 2025). | AI and automation. Preparing a document on the product flow. |

Akash, Deval and Bhoomi know each other well: they led the same student club in turn. Deval said the Smart India Hackathon had about 78,000 participants.

### Ideas discussed

1. **Heat and the MOM rest-break rule (Rafael).** MOM rules say employers must give rest breaks during heavy outdoor work when the WBGT heat-stress level is high. So the employer, not the worker, carries the productivity cost of heat. Possible product: insure employers (for example construction firms) against that lost productivity. Devnavin liked this most: "having insurance for the rule is such a gap". *Corrected: the threshold is WBGT 32°C and above (Rafael's notes and the Meet transcript). The Hermes transcript misheard it as "22".*
2. **Grab / delivery riders (Rafael).** They are exposed to heat and are not covered. Devnavin's counterpoint: platforms have weak duties toward gig workers, and they act mainly under government pressure. Construction is where the rule makes employers act.
3. **SME income loss (Rafael, Deval).** Example: a hawker who cannot trade during a storm has no physical damage but still loses income. Deval's version: estimate each SME's daily income (from tax or sales data) and pay that daily amount when the trigger fires.
4. **Data gap (Rafael).** The NEA WBGT API on data.gov.sg only has data up to about February 2025, roughly 2 years. That is too short for a back-test. Bhoomi and Deval proposed generating synthetic data with several LLMs, cross-checked, and combined with the official APIs.
5. **Framing (Devnavin).** This track is judged on the insurance product (cost, distribution, policy design), not mainly on the tech. Deval answered that the policy and the ML model that evaluates the data matter equally.
6. **Parametric framing (Rafael, Dewa).** Income wants cover that pays on a disruption, not only after damage or injury.

### Decisions and plan

- Finish most of the build **before** arriving in Singapore. Use the hackathon days for polish, extra features, and changes from judges' feedback.
- **Ground research in Singapore:** Devnavin offered to survey SME owners. Bhoomi asked for photos and videos to put in the pitch, to show real demand.
- Use the GitHub repo as the shared place for all work, including data and synthetic edge-case data. Clean up later.
- Dewa said this is a case-study style hackathon. Rafael agreed: "It's more of a case study hackathon."
- AI tools: Dewa has Claude Max, DeepSeek and Grok. Rafael has Claude Pro. Bhoomi warned that her company Claude account cannot be used from Singapore (IP change risk), so the team may buy a Max plan there. Organisers may also give free credits (date unknown).

### Action items (corrected with the Google Meet notes)

Bhoomi proposed these near the end. The Hermes transcript heard the data task as "Deval". The Meet transcript and Gemini's action list give it to **Dewa**, and Deval is paired with Bhoomi on architecture, so Dewa is the likely owner.

| Who | Task |
|---|---|
| Devnavin | On-ground survey of SME owners in Singapore, with photos and videos. Send sample policy documents (general insurance, cyber). Send his GitHub account to Dewa. |
| Rafael | Research and product design: what the product looks like, how it insures users, features. Share his notes (done: `docs/resources/rafael-research-notes.md`). |
| **Dewa** | **Data creation: "synthetic data using LLMs and API endpoints" before the next meeting.** |
| Bhoomi (with Deval) | Technical architecture. Share her workflow PDF. |
| Deval | Notion page with the final decisions. Review the Singapore context documents. |
| Akash | No task assigned out loud. |
| Everyone | Read the Singapore policy documents from Devnavin before the next meeting. |

**Next meeting:** "day after tomorrow", which is Monday 9 Nov 2026. The time was said as "ten forty". Confirm the time in the group chat.

## Transcript reliability

- 7 speaker labels were found for 6 people. Mapping used: SPEAKER_0 = Devnavin, SPEAKER_1 = Dewa, SPEAKER_2 = Akash, SPEAKER_3 = Deval, SPEAKER_4 = Bhoomi, SPEAKER_5 = Rafael, SPEAKER_6 = **"Akash?" (probably wrong)**. The Meet transcript shows Akash spoke only 11 times, all early in the meeting. SPEAKER_6 lines are most likely Devnavin or Deval. Check the Meet transcript for any line that matters.
- Turn boundaries are often shifted by a few words: the end of one person's sentence appears at the start of the next person's line.
- Known label errors:
  - 03:28: Rafael's first introduction ("I'm Rafael. I'm a Singapore Polytechnic student...") is under Akash's label.
  - 06:02: the line starts with other voices ("AI-powered financial app. Love it. Akash, wanna go?") before Akash's own introduction.
  - 13:06: the start ("I firmly believe Devnavin will play a very crucial role...") is another person talking about Devnavin. Devnavin replies at the end.
  - 34:48: the proposal to survey business owners on the ground is under "Akash?", but from context it is probably Devnavin (Bhoomi replies "while you go to do the industry visit").
  - Bhoomi's label (41 turns) probably includes some lines from other people.
- Speech-recognition errors in names: "Sky" = Akash. "Gumi", "Umi", "Bumi", "Bhumi" = Bhoomi. "Dave" = Devnavin. "Deva" = Dewa. "Devasan" = Dewa. "Tafel" = Rafael. "Cloud" = Claude. "Codecs" = Codex. "element" / "elements" = LLM / LLMs. "motion" = Notion. "WGPT" / "WBGP" = WBGT.

## Full transcript

**[00:00:00] Devnavin:** Did have it long term enough. I will take it out and I'll send it to

**[00:00:03] Dewa:** you.

**[00:00:06] Devnavin:** By the way, I think all of you guys are tech guys. I'm a non-tech guy here. I'm more of a insurance guy. That's great.

**[00:00:10] Dewa:** That's

**[00:00:13] Devnavin:** great. Especially with the section insurance. Why not on the team? Yeah. So, so for context, is, I'm a licensed advisor here for, for the general insurance topic. You hear it's something like general insurance, it, or say put on the slide insurance, with investment-based insurance, India is really big insurance for that. Then the third category is called general insurance. This is your motor insurance, cyber insurance, all those very creative things there. I'm licensed in all of them. I specifically focus on because it's like I'm a general insurance license, solo provider. The only thing I solo is motor insurance, and I'm so worried about it. Stuff that has so much exciting things. I said, okay, let me use this as an excuse to go and learn what would really sound. So yeah,

**[00:01:03] Akash:** that's actually the perspective. Hey, how about we make use of this time, we introduce ourselves, and talk about our background, what our skills, and what we can contribute to the team from delayed.

**[00:01:25] Dewa:** Sure, maybe I'll start first. So, everyone.

**[00:01:29] Devnavin:** Sky, can we wait for five

**[00:01:31] Dewa:** minutes? Oh, sure, sure.

**[00:01:37] Devnavin:** On a funny note, me and Deva are in the same class.

**[00:01:40] Dewa:** Yes.

**[00:01:41] Devnavin:** Yeah. Sky, Gumi, and me, we are like three generations.

**[00:01:49] Deval:** Gumi is my just senior in the college, and Sky is my super senior.

**[00:01:54] Devnavin:** Wow.

**[00:01:54] Deval:** Sky junior is Gumi, her junior.

**[00:01:59] Devnavin:** I am ready.

**[00:02:00] Deval:** I mean, I've worked with each other a lot in lot of hackathons and not, like other, other products.

**[00:02:07] Dewa:** And I saw you guys also went for the last year's Singapore India Hackathon, is it?

**[00:02:13] Deval:** Not Singapore India Hackathon, it was Smart India Hackathon. So that was the, India's biggest and you can say it as the world's toughest hackathon. There was seventy-eight thousand people participated in that in the initial round after multiple rounds. In the finals, in a tournament statement only five teams were there. And only, like, if I tell you, approximately out of seventy-eight thousand teams, only twelve hundred winners were

**[00:02:42] Akash:** there.

**[00:02:43] Dewa:** So

**[00:02:44] Deval:** for Singapore India Hackathon, last year twelve hundred winners, they took all of them, then they did multiple rounds, and they shortlisted sixty people out of those.

**[00:02:55] Devnavin:** Seriously, two on the pro, oh my

**[00:02:57] Akash:** god.

**[00:03:01] Deval:** He completed with seventy-eight

**[00:03:05] Dewa:** thousand people to get

**[00:03:06] Akash:** here. In hundred games. In hundred games. Awesome.

**[00:03:11] Dewa:** How about you, Rafael? Do you also participate in hackathons and all this stuff?

**[00:03:16] Akash:** yeah, actually, I'm,

**[00:03:18] Deval:** I grind hackathons.

**[00:03:21] Devnavin:** And then he's, and he's participate, accept, I admitted, and he participate.

**[00:03:26] Deval:** Okay.

**[00:03:26] Dewa:** As you were saying?

**[00:03:27] Devnavin:** Oh,

**[00:03:28] Akash:** easier. Oh, easier. Okay, okay. I'm gonna start with my introduction. I'm Rafael. I'm a Singapore Polytechnic student. I also grind a lot of hackathons. I actually won a few notable ones. one is the Singapore BET Hackathon, which is for entrepreneurs where they basically pitch their ideas to the judges, and then they can get funding. So I managed to get, like, first and finalists for two of those competitions. Then I also win first place on NUS Actor Good, which is basically a social cause hackathon. So the, the project, we made a project for, like, boys' home, and then we're actually got, we're actually actively implementing it with the boys from the Muhammadiyah Welfare Home. So that's another thing also. Actually, the way I got, in, I actually didn't know about this hackathon. It's my first time hearing about it, when this SMU lecturer, like, reached out to me via LinkedIn and say, oh, Rafael, we're looking for, builders such as yourselves who want, like, the NUS Actor Good, and then now I'm here, I just apply and say, oh, I am free. Why, might as well just go for this hackathon as well. Yeah.

**[00:04:42] Devnavin:** So

**[00:04:50] Dewa:** that is basically my

**[00:04:50] Devnavin:** background here. Thank you. You were invited into this. That's amazing.

**[00:04:53] Dewa:** Yeah. So, I'm from the same school as Dave. We're from SMU, and we're both here too. I'm taking information systems, and I also participate in a few hackathons this past few years. I think I participate in around, around like ten-ish, and I won five, but most of them are, school level hackathons. And I think this one is, is my biggest hackathon yet. So I'm pretty, pretty keen on winning this one as well. And yeah, right now, we're actually in the, in the entrepreneurship class, me and Dave, and we're building, and we're working on our own enterprises. Myself, I'm currently now working on a budgeting app, but What's different is that instead of manual inputting, you input screenshots so that it automatically categorizes for you and detects the rows. And yeah, currently it's on App Store and, and, and Play Store as well. So, I'm more on the technical side. I like building, and I hope I can contribute on that as well in the, in the second one.

**[00:05:51] Devnavin:** Awesome.

**[00:06:02] Akash:** And one more thing, yeah, yeah, that's AI-powered financial app. Love it. Akash, wanna go? Let's go. Oh, yeah. if you don't mind, I'll go next. so, I guess, Amartash, you can finish for me, I guess. I'm actually in Brooklyn right now, Brooklyn, New York. having a lot of fun. And, in terms of, in terms of my platform is, so I've on, seven hackathons before. one of them was actually in Singapore, so I've been to Singapore before. we had a hackathon called, Hagglobal. So that was like, people from all around the world, we had to be in our national level high school, so we won the India round, and then we came to Singapore, and then we were top nine. we were the only team from India in the top nine, but I just beat lots of the top nine round. that was when I was in university. I, it's been nine months. seven, eight months since I graduated, I worked for a US startup called Study, and I worked a lot on infra, I worked a lot on DevOps, MLOps, and I've also worked on fintech before. So yeah, my courses are basically, building and prototyping really fast. I'm really good with leadership, I'm really good with presentations, I'm really good with speaking on stage. I am actually in the US for an international conference where I'm speaking at, and yes, actually me, Deval, Umi, we are all from the same university. we're part of the same club, and my, college degrees. So yeah, all three of us are really looking forward to working with you guys. And yeah, looking forward to winning this, at the university. Cheers.

**[00:07:30] Dewa:** Oh, would you mind sharing about the club? What club was it?

**[00:07:34] Akash:** it's called Portland. it's like the student open source community of India. they actually, they student open, in September as well. And yeah, so right now, so basically I used to lead the club and my university guys, then Bumi used to lead it, and now they will lead it. So it's like three years of, senior junior relationship and leadership, from us.

**[00:08:00] Dewa:** Oh,

**[00:08:00] Devnavin:** that's cool. So lovely, so lovely. My God, the chemistry is so good.

**[00:08:06] Akash:** all right. looking forward to working with you guys. Looking

**[00:08:09] Devnavin:** forward. Will you be coming to Singapore? Will you be coming to Singapore? Yes. Awesome.

**[00:08:14] Deval:** Please tell me the...

**[00:08:15] Akash:** Of course, of course.

**[00:08:16] Devnavin:** Okay.

**[00:08:16] Akash:** I'll be flying from US to Bangalore, and same day I'm gonna take the flight to Singapore.

**[00:08:21] Devnavin:** Long flight, man. Oh my God. Indeed. Okay, who would like to go next?

**[00:08:29] Deval:** should I go?

**[00:08:30] Dewa:** Sure.

**[00:08:31] Deval:** So my name is Deval Gupta. I currently working as a, ML engineer at a startup called Awesome Sleep. I also do the, app development, for both iOS and Android. I have built like four internships there. I am also good at cybersecurity and new learning systems. I am also a tech guy. other than that, I have, like, five hackathons. I do cybersecurity competitions as well. And hackathons includes like India's biggest hackathon and world's toughest hackathon as well. So yeah, that's me.

**[00:09:12] Devnavin:** Amazing. Over to you, Steve. Umi, can I hear you? yeah. Hi. Hi, everyone.

**[00:09:29] Bhoomi:** Thank you. Nice to see you all here. Well, and thank you for your time. Okay, so introducing myself and, I'm Bhumi and I'm currently a panelist student from Bangalore, India, and as Akash already said that we are from the same college and, community point of view. And I'm also a tech girl here. So, yep, I have done previously about the code sessions and I've met AI builders and private as an AI engineer. I love building up things, automating things up, and just wherever I can put AI and automate the things up so that my work flows easy and wherever I can relax myself using the tech things. So that's the whole purpose. Regarding the hackathons, like I have qualified hackathons before and I have won the, twice the smart India hackathon. I got selected here in the last ten years, so I was a governor of it on twenty twenty-four and twenty twenty-five, and let's see if it goes ahead this time or not. And yeah, obviously interested in winning, Singapore India, I guess that would be a great thing, and yeah, ready to put all my efforts there.

**[00:10:40] Devnavin:** Awesome stuff. Awesome stuff. Very well. Thanks. Okay, so unlike all of you, I've never been a entrepreneur in my life. That's what I mean. I'm not a tech guy, so I, but I'm not that guy. I'm more like a fun business guy who could talk to people very interestingly. So what I actually do, me and Deva are from our entrepreneurship class. I run my own business. I am in the insurance industry. I'm a financial planning, thing. The way I, people know me through my Instagram. I can just quickly share. This is my Instagram, and I specifically do financial planning for Indian expats, NRIs, Indian. So a lot of my clients are like, find me through Instagram and my story and all the acres can eat up, but I work for this company called Financial Alliance. It's my own practice, but I get to partner with all these different insurance platform, like for the work that we're doing, the competition that we are doing in, it's called General Insurance. And these are the General Insurance partners that we have. So literally, income is one of our partners. So that doesn't mean I know how to, do all these products. I have limited myself to like, investments and insurance, like life insurance, kind of business, and for general insurance, like very basic travel and like motor insurance. But during this hackathon, what we're doing is like more complex, more creative version of our general insurance product. So if there's any help that's needed when it comes to Contacting you, the medium, to bounce off some ideas within the companies, I can always put my strengths there. And one of my other skills that is, if you need to go and test this idea to a actual company, I have connections, business owners in Singapore, small medium business owners, because that's one of our arguments, right? SMEs. I have a few SMEs who are my clients also. I can just go and talk to them and say, I know we didn't do any general insurance, but hey, this is an idea that we have this thing will work for you. If it's useful, happy to do that. So I'm more like the fun, chill guy. So that is my specialization. Okay. Yeah. That's pretty

**[00:12:51] Bhoomi:** cool. Like taking my risk background, having a strengths of risk background, like, detect potentially all of those things, because we have to build expressivity for Singapore. So yeah, that would be a huge advantage for us.

**[00:13:06] Devnavin:** Awesome. I firmly believe, right, Devnavin will play a very crucial role in this team because a lot of us are tech guys, and you have like the domain expertise in insurance, which I feel is gonna be very helpful, especially as us tech guys, we think like a certain way, so your inputs are gonna be really, really good for this. You guys are so... I'm gonna have like, don't know anything about tech. I'll help you as, as much as possible.

**[00:13:30] Bhoomi:** We are on a perfect combination, like people with tech, people with presentational skills, and yeah, obviously by the street track. So we can get all the knowledge and build it as well. Awesome stuff.

**[00:13:45] Rafael:** Okay. Now that introductions are out of the way, we can start and look at the problem statement and bounce some ideas around, get some, get some thoughts, uses going.

**[00:13:55] Bhoomi:** Yeah. Sorry to interrupt, like Rafael and Devasan, just give me a short introduction of your two, like, what domain you work on, just be, I was

**[00:14:07] Dewa:** Okay, sure. Oh, you want to go first?

**[00:14:10] Rafael:** I go, you go first.

**[00:14:12] Dewa:** Yeah, so I'm in the same school as Dave. I'm a year two information system student, so I'm also a tech guy. I've also joined a few hackathons, win five school level com, school level hackathon, and this is my biggest hackathon yet. And I'm very interested to win with you all. Yeah. Okay.

**[00:14:26] Bhoomi:** Now I'm

**[00:14:27] Dewa:** Rafael,

**[00:14:31] Rafael:** I'm a Singapore Polytechnic student. I won quite a few hackathons myself as well. One is the NUS Hackerwood, one is the Singapore Baby Challenge and Baby Hackathon, which is, an entrepreneurship hackathon hosted in Singapore Poly, where you can say like startup ideas and present it to the judges, one of, one, one of which is Jan Hau Tan, which is like a big, very big influence of you. So I'm very well versed in these hackathons. my experience in, like, professional, technology product manager in Prudential. So I have a bit of, insurance experience, but not as much as Devnavin over here. And yeah. So what I can contribute to the team is, I can help in prototyping as well, and coming up with the proper problems that we can tackle, and very, very deep, very deep in research as well. Yep. That's basically production for me. And

**[00:15:33] Bhoomi:** that's on the sales part as well, as well as, like, what, what are the places we can expand the product on, what parts we can use that, right?

**[00:15:41] Rafael:** Yeah,

**[00:15:42] Bhoomi:** exactly. Beyond the engineering side, outside of the project, right? Yep. Great.

**[00:15:52] Devnavin:** Hello. So I know that Rafael has some things he has done, and maybe have shared document he can share with us, and then he can also, if you guys have done your own document, take turns. Like, let's start from somewhere.

**[00:16:06] Rafael:** Okay, sure. Maybe I can share my screen. I did some rough notes. It may be, all over the place, but this is just the

**[00:16:14] Devnavin:** notes that I've taken. Okay? So I may

**[00:16:27] Rafael:** share. Hey, you can, can you see my screen? that's the one I'm sharing right now. yes. So these are the rough notes that I've taken after doing a bit of background research for this, problem statement. So of course, these are, some of these are taken from the From the document the income insurance provided us. So these are the important one is, which is the, what is in scope and what is out of scope. I feel like we should really like familiarize with ourselves with the, what's considered out of scope because we don't want to waste our time like doing stuff that is not really relevant to what income is looking for. So I already put it here in my notes, so we can keep that in mind. And we also have the constraints here. So all of this you can find on the notes as well, but I just don't want to put them on my notes. So now the important thing is, the research. So as a, I have a background in product management, so I want to practice my product thinking in a sense like knowing, what are the pain points in the problem itself. So the three main things that I found out is Who pays, which means, who pays for the product, maybe the businesses, maybe individuals, and so forth. We really need to know, what are those? And does it pay when I'm actually hurt? So one of the, one of the problems that the presenter for the income insurance, when you went for that previous, call they made, right, is should they pay, but they, their payment is too late, or they pay like, what, a few weeks down the line, which when they need the money now. So we really need to get this figured out as well. And of course, can income run it profitably at scale? So we must think of the product, how is it sustainable for them, like the pricing and all of this, which I feel like Devnavin can help a lot in that area. Okay. So here are the terms that I found out is Wet bulb globe temperature, which is basically the The ship, how they track the ship for Singapore, which they also include like air, dry temperature, region ship, and wind speed and movement. So it's basically a more gated ship tracking mechanism for Singapore, so it also track like all of these, important data points as well. So, okay, now, now that definitions are out of way, basically, let's scroll down. Data. Okay, I think my notes app is bugging right now. Hi, Darrell. Hey, now, I hear the, the research I done. So I look at the, the Webull Global Temperature API, right, and the data there is only until February 2025, so only two years. When the, when the income insurance presented there, we must do like some backtesting, right? I feel like two years is not enough of a data set. So I found that maybe there's an opportunity here where we can use our data and AI skills, because these data are also, out there, like way before, like, a decade, but they're not, they're, they're just not in the WGPT API, so maybe we can do some tech magic there. There's an opportunity there for it.

**[00:20:10] Bhoomi:** Because the data is still there, but, yeah. you

**[00:20:12] Rafael:** can go ahead.

**[00:20:15] Bhoomi:** From the meeting, the, the host of this conference statement was actually saying about that we can, synthesize, we can create our own data, like synthetic data, as per the AI at the We can actually make the data file, data for different kind of edge cases and like cover those edge cases specifically. It's very tough to get the data of different kind of situations, right? So we can actually get it for the, over the period of time, like ten years, and we can show that how our AI is generating those data and how we are actually taking the important aspects of those data points. So that we can do that in a good way as well, in accordance with this WG.

**[00:20:57] Rafael:** Exactly. As, she put it, like correctly as well. This is what I'm, this is an opportunity that we can make. If we can manage to solve this, it will be good. So that's one opportunity for us. And I also did a bit of research on what is our Ministry of Manpower's, HIIT rules, which is basically the rules that they must follow up. So actually, right, one interesting thing is, WBGT twenty-two Celsius and above, employers must give a minimum of ten minute rest break every hour for heavy physical work. So what this means, right, for those working like, let's say, construction worker jobs, the ones paying for, extreme heat, right, are not the employees themselves, but the employers, because they're paying for it in productivity, in a sense, right? Because, of course, the workers must have ten minutes breaks. So the one really taking the cost here is the employers, so that's one angle we can look at it as well. And this frames it like the heat problem is for the employers. Yeah. That is smart. That is good. And for the, the gap, right, when I look at the, the notes, Mom has already answered it, the work site versus station gap. Only construction sites worth for five million or more, shipyards and process industry need their own WBGT meter. So everyone else, right, they can just take the readings on the ADA, my AMD app. So that's also one data point. So here are the pain points that I listed for the, for this problem statement. May I have a question

**[00:22:51] Akash?:** before you move on? When you talked about wet bulb temperature sensor, that temperature body, why did we focus on that? Is it something that was mentioned in the notes to focus on that, or did you choose that?

**[00:23:04] Rafael:** Oh, no. No, no, no, no. This one is just one way of looking at it. We can also look at floods as well, but this is only based on the data that the resources that they give on the On the industry strike problem statement. Okay, so, yeah, so we're not like entirely like pigeonholed to this heat, but if we're going for a heat, these are like things to keep in mind, is basically what I'm saying. Yep.

**[00:23:34] Akash?:** I believe it's very nice. So if you want, one thing I, rephrase what you just said was, for the heat drop down, one of the insurance products you're suggesting potentially, not just a confirmed one, but like when there's high heat, MOM regulates ten minutes break. So therefore, it's insurable event, because it's not coming out of the employer package. It's a rare event, but it does happen sometimes. They calculate the risks involved, and the insurers can pay for it. I love it, because it's something that Cause most of things of thinking of like mega trends is really, this, this is something that really, which is very hard to come up with. So basically, we have to design both ways, like how a user will get, get the benefits and how the company will also get the benefits. You have to think about both the perspective and design, design the product in such a way.

**[00:24:24] Rafael:** Yeah. Okay, actually, all right. One interesting, audience, the user, the one that will pay for this, right, are actually like, you know, grab delivery drivers. This, they're not covered under this, if you think about it. And then they're exposed to like hot, hot suns because they're driving their bikes, their et cetera. So that's another angle to look at it, because they are not covered, and they are affected by this, and they're the exact users that I think income should also consider as well.

**[00:24:59] Devnavin:** Good, but, You have a good idea, like the problem with the Grab is, problem with the Grab is they are always like contract employees and there's no regulation to really protect them, the gig workers, and even for like CPS contribution or something that recently they announced was after, it's a government pressure thing. They didn't need to do it. They didn't really need to care about Grab. But what is useful is what is in there, it's in the construction sites. So many construction companies, like they would need to do the break. These are where the mandate is. The rule is amazing. So having insurance for the rule is such a gap that you found, which is very interesting. But yeah, let's keep going. You can share your slides, continuous, or like if that is all, we can get to next person also.

**[00:25:48] Rafael:** the pain points I think I discussed a bit earlier. So yeah, the user, end user's pain point, these are like more in-depth of things. I can just send it on the notion after. Sure. Yes. So I think that's mostly it on my side. thank you. Yeah, this is good. Thank you. Does anyone else have anything else to share? Not yet. I'm

**[00:26:08] Bhoomi:** preparing a paper of the whole flow, like how we'll be making it, but it still requires, like quite the zany as, like, to actually see the figures. Yeah. So yeah. I'll share the document as, as possible.

**[00:26:31] Deval:** yep. I was, I will share one motion, so, which will contain the final decisions that we all were aligned on. So, like, in today's meet, whatever we discuss, the final points, we will add it in motion, so it will help

**[00:26:47] Devnavin:** us for the reference in the future. I'm writing notes, right? Yeah. Yeah. Like, holding, not holding

**[00:26:55] Bhoomi:** my notes, but the conclusions that we...

**[00:26:57] Devnavin:** Yeah. Yeah. One thing I want to get a little bit of alignment in, this is one of those rare topics where it's not just the tech solution that is going to impress our audience, it's... Yeah. Product insurance product, so much about the costing, the distribution, so much of its idea kind of product. That is what they are evaluating. But the tech is useful to, but that is not the main thing. So it's important to understand, like, what your idea you said about getting data... Here on data or case census. I don't know what is it that I'm talking about, but in insurance product. It's not actually

**[00:27:37] Deval:** in this, in this product, one important thing is the policies that we will be providing, and the same importance will be carried by the AI, the ML, the model that we are using to evaluate those data. Because that should be very good.

**[00:27:54] Devnavin:** Yeah. I'm going to send you guys some policy documents of like similar general insurance products for cyber insurance, some creative insurances. Full document, we can take a look at it, and then we can go dissect it.

**[00:28:07] Bhoomi:** Now, today's live print would be very helpful if you could share us document that how a belief of like Singapore insurance policy, since we are aware of India, how it works, how the policies goes on. But, for Singapore to get the context and to actually better work on the ideas and to make a product for Singapore, we need to know more about the policies, the regulations that are more used to in Singapore, so that would be very helpful for us. Sure. Yes, I

**[00:28:31] Rafael:** understand. Yeah. And if I'm gonna put down my two cents here, actually, right, I think income is trying to innovate the way how insurance works, because these, they're trying to go for a more parametric solution, because I remember they mentioned on the call, right, one problem is for insurance, a damage must happen. Like, let's say, some tech Blackout or something, or some, some workers get injured or something, that that must happen first before they can get the insurance. Which I feel like income insurance is trying to, innovate this whole process where it's not necessarily anyone has to be injured, anyone, any blackout must happen, but if there is like a disruption that happen, let's say extreme heat, then people cannot work. Not exact damage is happening, but they want to ensure this kind of scenario, because it's still costing like companies and SMEs their money, but no damages has been done, if you know what I'm saying, right?

**[00:29:37] Bhoomi:** You can consider the COVID-19 situation as well, like the, even the families, the people who are not damaged, like who are not injured or any kind of illness, who are not suffering, even though they were not able to, take employment and to work, right? So for that kind of situation also, like, should, should be there, something like that.

**[00:30:01] Devnavin:** I think COVID insurance is like loss of income, is that what you're talking about?

**[00:30:05] Bhoomi:** Yeah. Loss,

**[00:30:06] Devnavin:** okay. Well, I mean, all insurance is a loss, it's a risk perception. So it's just, they don't have dire loss, that's what you're looking at. Yeah. This is interesting, this is something that I have been, looking, this is the email I got last time, something called cyber insurance. I'll send you a document of like how cyber insurance policies underwritten. I'm guessing this is one of the creative kind of insurances. There's a new one in the market. They, how do you classify a cyber risk? It's usually the, there's so many different types of general insurance, there's financial lines, if someone cheats your money director, gets sued, there's liability insurance, then there's someone tries to hack your system. Those kind of insurance exist. I'll send you the policy documents of those. They can take how they are written, exactly what is excluded, what is the claim, what is the blah, blah, blah. I won't owe you a meal, I'll send a couple, and if you want more, I'll send you more. But yeah, this will be

**[00:31:00] Bhoomi:** useful.

**[00:31:05] Devnavin:** Yeah. It's a

**[00:31:10] Dewa:** lot, yeah. So I just

**[00:31:11] Bhoomi:** send one or two.

**[00:31:14] Dewa:** Yeah. So the problem is the insurance is that it's, it only gets paid after the damage is done, so the, the thing that we're looking at is like sort of trying to, like pay before damage is done, is it? Like, like look for some sort of way to, like, know before damage is done. Is it?

**[00:31:39] Deval:** So

**[00:31:43] Bhoomi:** basically...

**[00:31:51] Rafael:** Basically, even view it, right? Let's say you're an SMB focus center, for example. You're selling chicken, all of this, right? And then let's say there's a typhoon that come, then tip, tip focus center. So technically, there is no real damage, but you lose a lot of money because you cannot run your business on still not selling anything.

**[00:32:15] Dewa:** Yeah.

**[00:32:16] Rafael:** Which is...

**[00:32:17] Akash?:** What if they do it like, for example, how Rafael, told that there is some typhoon. Now, we will be having the information of all the SMEs, like how much they earn approximately per day, based on the tax and whatever, like here we call it as idea what we sell. Now, based

**[00:32:38] Deval:** on that, we will be charging the insurance money for to them. And, for example, today the, SMEs don't have work. So they will get money credited based on their per day income. So for example, if, SME earns like hundred Singapore dollar per day. So same day they will get hundred Singapore dollar. So it

**[00:33:05] Akash?:** is also a good option, I guess.

**[00:33:09] Dewa:** Okay. Makes sense.

**[00:33:17] Devnavin:** Okay. So, when, when will you guys be reaching Singapore? What day is it? 1:14 morning.

**[00:33:26] Bhoomi:** Oh,

**[00:33:31] Devnavin:** okay. To, okay, do we wanna meet before that, like online again, or how shall we go about doing this?

**[00:33:39] Akash?:** Yes, we will finalize all the things and we will start building the product.

**[00:33:46] Bhoomi:** Before we bridge into Singapore only, we'll decide on the structure, on meetings, and we'll start building the things up. And we'll reach Singapore, we'll more on work on the polishing part, like what things we'll do, what, who polish will be needed, what extra features can be added, what polishes we can set up. Basically on the polishing part, we'll, make while we meet, and like the rest of the things we'll complete before that itself. You

**[00:34:11] Rafael:** know, one thing I want,

**[00:34:13] Deval:** whatever, whatever the, whatever, whatever, they asked us to build, we should complete it before the hackathon. And that we should focus more on the additional features that will

**[00:34:27] Akash?:** give us those points.

**[00:34:29] Bhoomi:** And then we can always put feedback to the judges, like we are already done with all this. so there's just more things that we can include in our project, so there's just more improvements that we can do, and on their suggestions, we'll implement all those things, and it will look like they said, and we. So that's always a plus point in half the thoughts to work.

**[00:34:48] Akash?:** I like that. I want to suggest if you disagree with me, I want to add one extra thing, sure, which is that you, I want to go down on the ground and do a survey on

**[00:34:58] Bhoomi:** some of the business owners, whether you like this policy. I think that's absolutely a lot of like, you know, points like, yeah. I would suggest like while you go to do the industry visit on whatsoever, maybe just make some videos and maybe take some pictures so that we can put on the presentation that actually will require people. We actually contacted them and what we are made is not just a prototype, it's actually the solution that people are wanting. So that we can present it.

**[00:35:31] Akash?:** We will present it as a ready to ship product that if you want, you can ship it today only and it will, it will benefit a lot of people.

**[00:35:41] Rafael:** Okay. In, in a presentation, right, I feel like the judges would really love it. It's a lot of money, and if we really put in all this effort, and we can

**[00:35:49] Bhoomi:** really make a good impression. Yeah. Honestly, I have been doing this for the past three years, and it's all, like, every time I visit the required PS, authorities, like, once I have made it for police department, I actually went to the police station, did all the research there, took the pictures, and they were really inspired, and the people have done groundwork. So that would be really helpful. I love it.

**[00:36:17] Dewa:** This is my first time doing a hackathon that it's not building, like, an app, actually. It's more of a document, right? Like, the final deliverable is a document for this one, right? Something like that, yeah. Document plus

**[00:36:27] Rafael:** some. It's more of a case study hackathon.

**[00:36:31] Dewa:** So I guess we can use the GitHub for, like, the, the, the data that we have and the, the, the, the Those are like the data we also heed, since the only data that we have is only two years from the API, right? Then we're going to have to make the data ourselves, like the edge cases that I think those can be put in the GitHub repository. Yeah. Everything that we are making began for the GitHub project. Later on, we can work on the cleanup

**[00:36:50] Bhoomi:** part,

**[00:36:51] Rafael:** but

**[00:36:52] Bhoomi:** for the time being, we can put everything there in the sense to need a, a source of work for everyone.

**[00:37:03] Dewa:** Yeah. So what's like the,

**[00:37:06] Akash?:** So can anyone tell me that is there any, like there will, there should be no problem with the synthetic data, data if we are generating data from other elements?

**[00:37:15] Bhoomi:** No, they actually said in the meeting itself, our owner of this partnership wanted to get data from data using elements.

**[00:37:23] Dewa:** What do you guys use actually?

**[00:37:26] Bhoomi:** we use like cloud that, we can use codecs and, even like different kind of element, we can combine them, giving prompts to each other and then making a perfect data set here.

**[00:37:37] Dewa:** Okay. Do you guys use multiple allies?

**[00:37:41] Akash?:** Like we can't rely on a single element to make the data. We have to cross-check it with multiple elements. That will give much better

**[00:37:51] Bhoomi:** data, but we need quality data.

**[00:37:52] Rafael:** And then

**[00:37:52] Bhoomi:** we'll, we'll merge it with the data even while the problem state with the, owner as well, like all the API elements they had given. we'll use that as well and create our own system, so that we do not miss on any part.

**[00:38:07] Dewa:** sure. So do you guys have like multiple, AI, AI subscriptions?

**[00:38:13] Bhoomi:** Yeah,

**[00:38:14] Akash?:** like I have my, I have my company store I can use that. Oh. We can also use that. I, I use that also as.

**[00:38:22] Bhoomi:** I do have, but the problem is like in Singapore, I cannot use my company cloud, so I'll be purchasing money.

**[00:38:29] Akash?:** Of course. Of course. If I don't

**[00:38:31] Bhoomi:** have, we can purchase one together there in Singapore for max plan of ten thousand rupee. Yeah, a

**[00:38:38] Akash?:** hundred dollars.

**[00:38:41] Bhoomi:** Sure. Because the problem is like it will switch IP from India to Singapore, no? The neutral plan and our, our cloud account will get bad.

**[00:38:49] Dewa:** But you can use a VPN, right?

**[00:38:52] Bhoomi:** Yep, but the VPN also like one of my friends was using from versus my whole cloud account called the hundred seven. So change of IPs, yep. So can't take us with company cloud. Yeah. For my side, I have a Cloud Pro subscription. I use it for developing projects. So

**[00:39:06] Rafael:** for me, that's what I have.

**[00:39:19] Dewa:** I have CloudMax and, some, I also have some DeepSeek API key, and I also have a Grok subscription. So I can, I can use

**[00:39:30] Bhoomi:** it.

**[00:39:35] Dewa:** Yeah. I think they're gonna also give us some free, credits as well. I don't know when will that come. Yeah.

**[00:39:43] Bhoomi:** Sorry? I'm from Dewa as well. Yeah.

**[00:40:03] Rafael:** Okay, right. before we conclude this meeting, right, maybe we could draft like some general plan going forward, like let's say, yeah, just a general plan on what we'll do until we report to each other next meeting. Yep. So, like, let's say, one does research on all this insurance, one, look at the data from the WBGP, all of this, some general thing to get us started, yeah.

**[00:40:47] Bhoomi:** What comes on my mind currently is, like, the, they will be best for the on-ground work, and if you guys in Singapore can collaborate and take pictures, then you all can perform for For your convenience. So you can do the groundwork and actually take the policies and the benefits of the, fintech industries, so I think that, they will be best for that. Tafel, you can do the, researching part and the product part of the, whole thing, like what the product should look like, how it will be insuring the users as well as the fintech companies, how they will be providing the insurance, all those details, what kind of features and what things will be this. And Deval, if it's fine, you can work on the data creation part, and it will also help you with that. Yeah, for the starting and, yeah, Deval and I can pan on the architecture, the things to be included here, and, how we'll make the whole, whole product, the technical aspect of the thing for the time being, yeah, for like, we can have the next meeting day after tomorrow, ten forty. Sure.

**[00:41:59] Dewa:** Sure, that sounds

**[00:42:00] Bhoomi:** good.

**[00:42:03] Devnavin:** Yeah, Monday is good for me, to me. First,

**[00:42:04] Akash?:** I have to, like, I have to read all the

**[00:42:08] Bhoomi:** accounts. Yeah. Yeah, we have to actually get the context for Singapore, so yes, they will to send us the documents, we'll go through it first, and, then we can do the rest of this time. Okay. Yeah. Sounds good for me. Yeah. Absolutely. Anything else for today's meeting? That's all. Okay. Nice. Nice

**[00:42:31] Dewa:** meeting you guys.

**[00:42:33] Rafael:** All right,

**[00:42:33] Bhoomi:** guys.

**[00:42:34] Akash?:** All right. I'll send the meeting notes.

**[00:42:37] Bhoomi:** Yeah.

**[00:42:37] Rafael:** Okay. Sure.

**[00:42:38] Bhoomi:** Bye.
