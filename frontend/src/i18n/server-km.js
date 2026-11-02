// Khmer translations for text produced by the Flask API (error messages,
// notification titles/bodies, security anomaly descriptions).
// The backend stays in English; the frontend translates what it shows.
import km from './km.js'

const st = (s) => km.enums[s] || s // status word, e.g. "live" -> "កំពុងប្រជុំ"
const reason = (s) => {
  const code = { Medical: 'medical', 'Official conflict': 'conflict', Travel: 'travel', Personal: 'personal', Other: 'other' }[s]
  return code ? km.enums[code] : s
}

// ----------------------------------------------------------------- exact messages
const EXACT = {
  // sign-in, accounts & passwords
  'Incorrect e-mail or password.': 'អ៊ីមែល ឬពាក្យសម្ងាត់មិនត្រឹមត្រូវទេ។',
  'Account is not active.': 'គណនីនេះមិនទាន់សកម្មទេ។',
  'This account is not active. Please use your invitation link or contact the Secretary.': 'គណនីនេះមិនទាន់សកម្មទេ។ សូមប្រើតំណពីលិខិតអញ្ជើញរបស់អ្នក ឬទាក់ទងលេខាធិការ។',
  'Authentication required.': 'សូមចូលប្រើប្រព័ន្ធជាមុនសិន។',
  'Invalid authentication token.': 'វគ្គចូលប្រើមិនត្រឹមត្រូវ។ សូមចូលប្រើម្តងទៀត។',
  'Wrong token type.': 'វគ្គចូលប្រើមិនត្រឹមត្រូវ។ សូមចូលប្រើម្តងទៀត។',
  'Session expired. Please sign in again.': 'វគ្គប្រើប្រាស់បានផុតកំណត់។ សូមចូលប្រើម្តងទៀត។',
  'Invalid authentication code.': 'លេខកូដផ្ទៀងផ្ទាត់មិនត្រឹមត្រូវទេ។',
  'That code is not valid. Check the time on your phone and try again.': 'លេខកូដនេះមិនត្រឹមត្រូវទេ។ សូមពិនិត្យម៉ោងនៅលើទូរស័ព្ទរបស់អ្នក ហើយព្យាយាមម្តងទៀត។',
  'Current password is incorrect.': 'ពាក្យសម្ងាត់បច្ចុប្បន្នមិនត្រឹមត្រូវទេ។',
  'Password is incorrect.': 'ពាក្យសម្ងាត់មិនត្រឹមត្រូវទេ។',
  'Password must be at least 8 characters and contain letters and numbers.': 'ពាក្យសម្ងាត់ត្រូវមានយ៉ាងតិច 8 តួ ដោយមានទាំងអក្សរ និងលេខ។',
  'This link is invalid or has expired.': 'តំណនេះមិនត្រឹមត្រូវ ឬបានផុតកំណត់ហើយ។',
  'This account is already activated.': 'គណនីនេះត្រូវបានបើកដំណើរការរួចហើយ។',
  'If the e-mail exists, a reset link has been sent.': 'ប្រសិនបើអ៊ីមែលនេះមាននៅក្នុងប្រព័ន្ធ តំណកំណត់ពាក្យសម្ងាត់ត្រូវបានផ្ញើហើយ។',
  'Password has been reset. You can now sign in.': 'ពាក្យសម្ងាត់ត្រូវបានកំណត់ឡើងវិញ។ ឥឡូវអ្នកអាចចូលប្រើបានហើយ។',
  'Password updated': 'ពាក្យសម្ងាត់ត្រូវបានប្តូរ',
  'Signed out': 'បានចាកចេញ',
  'Full name is required.': 'សូមបញ្ចូលឈ្មោះពេញ។',
  // users & roles
  'A user with this e-mail already exists.': 'មានអ្នកប្រើប្រាស់ដែលប្រើអ៊ីមែលនេះរួចហើយ។',
  'Only administrators can invite another administrator.': 'មានតែអ្នកគ្រប់គ្រងប្រព័ន្ធប៉ុណ្ណោះ ដែលអាចអញ្ជើញអ្នកគ្រប់គ្រងប្រព័ន្ធផ្សេងទៀតបាន។',
  'Only administrators can grant the Administrator role.': 'មានតែអ្នកគ្រប់គ្រងប្រព័ន្ធប៉ុណ្ណោះ ដែលអាចផ្តល់តួនាទីអ្នកគ្រប់គ្រងប្រព័ន្ធបាន។',
  'This user has not activated the invitation yet. Resend the invite instead.': 'អ្នកប្រើប្រាស់នេះមិនទាន់បើកដំណើរការលិខិតអញ្ជើញនៅឡើយទេ។ សូមផ្ញើលិខិតអញ្ជើញម្តងទៀត។',
  'You cannot deactivate your own account.': 'អ្នកមិនអាចបិទគណនីរបស់ខ្លួនឯងបានទេ។',
  'You cannot deactivate the last active Administrator.': 'មិនអាចបិទអ្នកគ្រប់គ្រងប្រព័ន្ធសកម្មចុងក្រោយគេបានទេ។',
  'You cannot remove the last active Administrator.': 'មិនអាចដកអ្នកគ្រប់គ្រងប្រព័ន្ធសកម្មចុងក្រោយគេចេញបានទេ។',
  'Vote weight must be between 1 and 100.': 'ទម្ងន់សំឡេងត្រូវនៅចន្លោះពី 1 ដល់ 100។',
  'A role with this name already exists.': 'មានតួនាទីដែលប្រើឈ្មោះនេះរួចហើយ។',
  'Built-in roles cannot be deleted.': 'មិនអាចលុបតួនាទីដែលមានស្រាប់ក្នុងប្រព័ន្ធបានទេ។',
  'Built-in roles cannot be renamed.': 'មិនអាចប្តូរឈ្មោះតួនាទីដែលមានស្រាប់ក្នុងប្រព័ន្ធបានទេ។',
  'Move the users to another role before deleting this role.': 'សូមផ្លាស់អ្នកប្រើប្រាស់ទៅតួនាទីផ្សេងជាមុនសិន មុននឹងលុបតួនាទីនេះ។',
  'The Administrator role must keep the role.manage permission.': 'តួនាទីអ្នកគ្រប់គ្រងប្រព័ន្ធ ត្រូវតែរក្សាសិទ្ធិគ្រប់គ្រងតួនាទី (role.manage)។',
  'Role deleted': 'តួនាទីត្រូវបានលុប',
  'Invitation sent': 'លិខិតអញ្ជើញត្រូវបានផ្ញើ',
  // meetings
  'Title is required.': 'សូមបញ្ចូលចំណងជើង។',
  'Invalid board classification.': 'ប្រភេទប្រជុំមិនត្រឹមត្រូវទេ។',
  'Invalid meeting role.': 'តួនាទីក្នុងប្រជុំមិនត្រឹមត្រូវទេ។',
  'The meeting must be scheduled in the future.': 'កិច្ចប្រជុំត្រូវកំណត់ពេលនៅថ្ងៃខាងមុខ។',
  'Duration must be between 5 minutes and 24 hours.': 'រយៈពេលប្រជុំត្រូវនៅចន្លោះពី 5 នាទី ដល់ 24 ម៉ោង។',
  'Quorum must be between 1 and 100 percent.': 'កូរ៉ុមត្រូវនៅចន្លោះពី 1 ដល់ 100 ភាគរយ។',
  'Occurrences must be between 1 and 24.': 'ចំនួនលើកត្រូវនៅចន្លោះពី 1 ដល់ 24។',
  'Recurrence must be none, biweekly, monthly or quarterly.': 'ការធ្វើម្តងទៀតត្រូវជា៖ មិនធ្វើម្តងទៀត រៀងរាល់ពីរសប្តាហ៍ រៀងរាល់ខែ ឬរៀងរាល់ត្រីមាស។',
  'Passcode must be 4–12 letters or digits.': 'លេខកូដចូលបន្ទប់ត្រូវមានពី 4 ដល់ 12 តួ (អក្សរ ឬលេខ)។',
  'A live meeting cannot be rescheduled.': 'មិនអាចប្តូរកាលវិភាគកិច្ចប្រជុំដែលកំពុងប្រជុំបានទេ។',
  'Only scheduled meetings can be cancelled.': 'អាចលុបចោលបានតែកិច្ចប្រជុំដែលបានកំណត់ពេល (មិនទាន់ចាប់ផ្តើម) ប៉ុណ្ណោះ។',
  'A meeting can be started at most 1 hour before its scheduled time.': 'អាចចាប់ផ្តើមកិច្ចប្រជុំបានមុនម៉ោងកំណត់យ៉ាងច្រើន 1 ម៉ោងប៉ុណ្ណោះ។',
  'Only a live meeting can be ended.': 'អាចបញ្ចប់បានតែកិច្ចប្រជុំដែលកំពុងប្រជុំប៉ុណ្ណោះ។',
  'Reminders can only be sent for scheduled meetings.': 'អាចផ្ញើការរំលឹកបានតែសម្រាប់កិច្ចប្រជុំដែលបានកំណត់ពេលប៉ុណ្ណោះ។',
  'Only the host, co-host or a user with meeting.host can do this.': 'មានតែអ្នករៀបចំ សហអ្នករៀបចំ ឬអ្នកមានសិទ្ធិដឹកនាំប្រជុំប៉ុណ្ណោះ ដែលអាចធ្វើសកម្មភាពនេះបាន។',
  'You are not invited to this meeting.': 'អ្នកមិនត្រូវបានអញ្ជើញឱ្យចូលរួមកិច្ចប្រជុំនេះទេ។',
  'You are not a participant of this meeting.': 'អ្នកមិនមែនជាអ្នកចូលរួមក្នុងកិច្ចប្រជុំនេះទេ។',
  'Choose at least one person.': 'សូមជ្រើសរើសយ៉ាងហោចណាស់ម្នាក់។',
  'The host cannot be removed.': 'មិនអាចដកអ្នករៀបចំចេញបានទេ។',
  'Participants can only be removed before the meeting starts.': 'អាចដកអ្នកចូលរួមចេញបាន តែមុនពេលកិច្ចប្រជុំចាប់ផ្តើមប៉ុណ្ណោះ។',
  'Participant not found': 'រកមិនឃើញអ្នកចូលរួមទេ',
  'Participant removed': 'អ្នកចូលរួមត្រូវបានដកចេញ',
  'Agenda item not found': 'រកមិនឃើញចំណុចរបៀបវារៈទេ',
  'Agenda item does not belong to this meeting.': 'ចំណុចរបៀបវារៈនេះមិនមែនជារបស់កិច្ចប្រជុំនេះទេ។',
  'meeting_id is required.': 'សូមជ្រើសរើសកិច្ចប្រជុំ។',
  "'to' must be after 'from'.": 'កាលបរិច្ឆេទ "ដល់" ត្រូវនៅក្រោយកាលបរិច្ឆេទ "ពី"។',
  // virtual room & attendance
  'Wrong meeting passcode.': 'លេខកូដចូលបន្ទប់មិនត្រឹមត្រូវទេ។',
  'The host has locked the room.': 'អ្នករៀបចំបានចាក់សោបន្ទប់ប្រជុំហើយ។',
  'The meeting is not live yet. The host must start it first.': 'កិច្ចប្រជុំមិនទាន់ចាប់ផ្តើមទេ។ អ្នករៀបចំត្រូវចាប់ផ្តើមជាមុនសិន។',
  'You are in the waiting room. The host will admit you.': 'អ្នកកំពុងនៅក្នុងបន្ទប់រង់ចាំ។ អ្នករៀបចំនឹងអនុញ្ញាតឱ្យអ្នកចូល។',
  'Only the host can admit participants.': 'មានតែអ្នករៀបចំប៉ុណ្ណោះ ដែលអាចអនុញ្ញាតឱ្យអ្នកចូលរួមចូលបាន។',
  'This participant is not in the waiting room.': 'អ្នកចូលរួមនេះមិនមែននៅក្នុងបន្ទប់រង់ចាំទេ។',
  'RSVP must be accepted, declined or tentative.': 'ការឆ្លើយតបត្រូវជា៖ ទទួលយក បដិសេធ ឬមិនទាន់ប្រាកដ។',
  // absence & proxy
  'Invalid reason code.': 'មូលហេតុមិនត្រឹមត្រូវទេ។',
  'You already have an absence request for this meeting.': 'អ្នកមានសំណើសុំអវត្តមានសម្រាប់កិច្ចប្រជុំនេះរួចហើយ។',
  'You cannot approve your own absence request.': 'អ្នកមិនអាចអនុម័តសំណើសុំអវត្តមានរបស់ខ្លួនឯងបានទេ។',
  'You cannot view this request.': 'អ្នកមិនមានសិទ្ធិមើលសំណើនេះទេ។',
  'You can only attach files to your own request.': 'អ្នកអាចភ្ជាប់ឯកសារបានតែទៅសំណើរបស់ខ្លួនឯងប៉ុណ្ណោះ។',
  'Files can only be added while the request is pending.': 'អាចភ្ជាប់ឯកសារបាន តែពេលសំណើកំពុងរង់ចាំប៉ុណ្ណោះ។',
  'Only your own pending request can be withdrawn.': 'អាចដកវិញបានតែសំណើរបស់ខ្លួនឯង ដែលកំពុងរង់ចាំប៉ុណ្ណោះ។',
  'Request withdrawn': 'សំណើត្រូវបានដកវិញ',
  'A member cannot be their own proxy.': 'សមាជិកម្នាក់មិនអាចធ្វើជាអ្នកតំណាងឱ្យខ្លួនឯងបានទេ។',
  'The member needs an approved absence request before a proxy can be assigned.': 'សមាជិកត្រូវមានសំណើសុំអវត្តមានដែលបានអនុម័តសិន ទើបអាចចាត់តាំងអ្នកតំណាងបាន។',
  'The absent member must be a voting participant of this meeting.': 'សមាជិកអវត្តមានត្រូវតែជាអ្នកចូលរួមដែលមានសិទ្ធិបោះឆ្នោតក្នុងកិច្ចប្រជុំនេះ។',
  'The proxy must be a voting participant who attends the meeting.': 'អ្នកតំណាងត្រូវតែជាអ្នកចូលរួមដែលមានសិទ្ធិបោះឆ្នោត ហើយចូលរួមប្រជុំ។',
  'The proxy holder is also absent from this meeting.': 'អ្នកតំណាងក៏អវត្តមានពីកិច្ចប្រជុំនេះដែរ។',
  'The proxy holder has delegated their own vote.': 'អ្នកតំណាងបានផ្ទេរសិទ្ធិបោះឆ្នោតរបស់ខ្លួនទៅអ្នកផ្សេងរួចហើយ។',
  'This member already has an active proxy. Revoke it first.': 'សមាជិកនេះមានអ្នកតំណាងរួចហើយ។ សូមដកហូតអ្នកតំណាងចាស់ជាមុនសិន។',
  'Proxy is already revoked.': 'អ្នកតំណាងនេះត្រូវបានដកហូតរួចហើយ។',
  // minutes
  'Minutes cannot be written for a cancelled meeting.': 'មិនអាចសរសេរកំណត់ហេតុសម្រាប់កិច្ចប្រជុំដែលបានលុបចោលបានទេ។',
  'Minutes can be published only after the meeting has ended.': 'អាចចេញផ្សាយកំណត់ហេតុបាន លុះត្រាតែកិច្ចប្រជុំបានបញ្ចប់។',
  'Write and save the minutes before publishing.': 'សូមសរសេរ និងរក្សាទុកកំណត់ហេតុជាមុនសិន មុននឹងចេញផ្សាយ។',
  'Only published minutes can be sealed.': 'អាចបោះត្រាបានតែកំណត់ហេតុដែលបានចេញផ្សាយរួចប៉ុណ្ណោះ។',
  'There are no minutes to export yet.': 'មិនទាន់មានកំណត់ហេតុប្រជុំសម្រាប់នាំចេញទេ។',
  'Version not found': 'រកមិនឃើញកំណែនេះទេ',
  // voting
  'Invalid rule.': 'វិធានបោះឆ្នោតមិនត្រឹមត្រូវទេ។',
  'Rule must be simple, two_thirds, three_quarters or unanimous.': 'វិធានបោះឆ្នោតត្រូវជា៖ សំឡេងភាគច្រើន, ភាគច្រើន 2/3, ភាគច្រើន 3/4 ឬឯកច្ឆន្ទ។',
  'Give at least two different options.': 'សូមផ្តល់ជម្រើសយ៉ាងហោចណាស់ពីរផ្សេងគ្នា។',
  'Only draft ballots can be edited.': 'អាចកែប្រែបានតែការបោះឆ្នោតដែលនៅជាសេចក្តីព្រាងប៉ុណ្ណោះ។',
  'Only draft ballots can be deleted.': 'អាចលុបបានតែការបោះឆ្នោតដែលនៅជាសេចក្តីព្រាងប៉ុណ្ណោះ។',
  'This ballot has already been launched.': 'ការបោះឆ្នោតនេះត្រូវបានបើករួចហើយ។',
  'Votes can only be launched while the meeting is live.': 'អាចបើកការបោះឆ្នោតបាន តែពេលកិច្ចប្រជុំកំពុងដំណើរការប៉ុណ្ណោះ។',
  'Voting window must be 0–240 minutes (0 = until closed manually).': 'រយៈពេលបោះឆ្នោតត្រូវនៅចន្លោះ 0–240 នាទី (0 = រហូតដល់បិទដោយដៃ)។',
  'Voting is closed for this ballot.': 'ការបោះឆ្នោតលើសំណើនេះត្រូវបានបិទហើយ។',
  'A vote has already been cast for this member.': 'សមាជិកនេះបានបោះឆ្នោតរួចហើយ។',
  'You must be present in the meeting to vote.': 'អ្នកត្រូវតែមានវត្តមានក្នុងកិច្ចប្រជុំ ទើបអាចបោះឆ្នោតបាន។',
  'A proxy holder must be present in the meeting to vote.': 'អ្នកតំណាងត្រូវតែមានវត្តមានក្នុងកិច្ចប្រជុំ ទើបអាចបោះឆ្នោតបាន។',
  'You are not the appointed proxy for this member.': 'អ្នកមិនមែនជាអ្នកតំណាងដែលបានចាត់តាំងសម្រាប់សមាជិកនេះទេ។',
  'This member is not a voting participant of the meeting.': 'សមាជិកនេះមិនមែនជាអ្នកចូលរួមដែលមានសិទ្ធិបោះឆ្នោតទេ។',
  'Assign a voting proxy first (Absence & Proxy module).': 'សូមចាត់តាំងអ្នកតំណាងបោះឆ្នោតជាមុនសិន (នៅផ្នែក ការអវត្តមាន និងអ្នកតំណាង)។',
  'Only an open ballot can be closed.': 'អាចបិទបានតែការបោះឆ្នោតដែលកំពុងបើកប៉ុណ្ណោះ។',
  'Results are visible after the vote closes.': 'លទ្ធផលនឹងបង្ហាញ បន្ទាប់ពីបិទការបោះឆ្នោត។',
  'Close the vote before recording the resolution.': 'សូមបិទការបោះឆ្នោតជាមុនសិន មុននឹងកត់ត្រាសេចក្តីសម្រេច។',
  'Close the vote before exporting the summary.': 'សូមបិទការបោះឆ្នោតជាមុនសិន មុននឹងនាំចេញសេចក្តីសង្ខេប។',
  'A resolution has already been recorded for this ballot.': 'សេចក្តីសម្រេចសម្រាប់ការបោះឆ្នោតនេះ ត្រូវបានកត់ត្រារួចហើយ។',
  'Vote recorded': 'បានកត់ត្រាការបោះឆ្នោត',
  'Ballot deleted': 'ការបោះឆ្នោតត្រូវបានលុប',
  // documents & uploads
  'Choose a file to upload.': 'សូមជ្រើសរើសឯកសារដើម្បីផ្ទុកឡើង។',
  'The file is empty.': 'ឯកសារនេះទទេ។',
  'File is too large (max 10 MB).': 'ឯកសារធំពេក (អតិបរមា 10 MB)។',
  'Invalid classification.': 'កម្រិតសម្ងាត់មិនត្រឹមត្រូវទេ។',
  'Classification must be internal, confidential or strictly_confidential.': 'កម្រិតសម្ងាត់ត្រូវជា៖ ផ្ទៃក្នុង សម្ងាត់ ឬសម្ងាត់បំផុត។',
  'Cannot upload documents to a cancelled meeting.': 'មិនអាចផ្ទុកឯកសារឡើងសម្រាប់កិច្ចប្រជុំដែលបានលុបចោលបានទេ។',
  'Downloading is restricted for this document. Use the secure viewer.': 'ឯកសារនេះត្រូវបានហាមមិនឱ្យទាញយក។ សូមប្រើកម្មវិធីមើលឯកសារដោយសុវត្ថិភាព។',
  'You cannot download this file.': 'អ្នកមិនមានសិទ្ធិទាញយកឯកសារនេះទេ។',
  'Document deleted': 'ឯកសារត្រូវបានលុប',
  // reports, notifications, audit
  'Unknown report. Use attendance, voting or compliance.': 'មិនស្គាល់ប្រភេទរបាយការណ៍នេះទេ។ សូមជ្រើសរើស វត្តមាន ការបោះឆ្នោត ឬអនុលោមភាព។',
  'Notification not found': 'រកមិនឃើញការជូនដំណឹងទេ',
  'All notifications marked as read': 'ការជូនដំណឹងទាំងអស់ត្រូវបានសម្គាល់ថាបានអាន',
  'Already acknowledged.': 'បានទទួលស្គាល់រួចហើយ។',
  'There are no new log entries to archive.': 'មិនមានកំណត់ត្រាថ្មីសម្រាប់រក្សាទុកក្នុងបណ្ណសារទេ។',
}

// ----------------------------------------------------------------- dynamic messages
const PATTERNS = [
  [/^Permission denied: requires (.+)$/, (m) => `អ្នកមិនមានសិទ្ធិធ្វើសកម្មភាពនេះទេ (ត្រូវការសិទ្ធិ៖ ${m[1].split(', ').map((c) => km.perms[c.replace('.', '_')] || c).join(', ')})។`],
  [/^Account locked after too many failed attempts\. Try again after (\S+) UTC or reset your password\.$/,
    (m) => `គណនីត្រូវបានចាក់សោ ដោយសារបញ្ចូលពាក្យសម្ងាត់ខុសច្រើនដងពេក។ សូមព្យាយាមម្តងទៀតក្រោយម៉ោង ${m[1]} UTC ឬកំណត់ពាក្យសម្ងាត់ឡើងវិញ។`],
  [/^Missing required field\(s\): (.+)$/, (m) => `សូមបំពេញព័ត៌មានដែលតម្រូវ៖ ${m[1]}`],
  [/^File type \.(\S+) is not allowed\. Allowed: (.+)$/, (m) => `មិនអនុញ្ញាតប្រភេទឯកសារ .${m[1]} ទេ។ ប្រភេទដែលអនុញ្ញាត៖ ${m[2]}`],
  [/^Invalid (\w+): use ISO format, e\.g\. (.+)$/, (m) => `ទម្រង់កាលបរិច្ឆេទ ${m[1]} មិនត្រឹមត្រូវទេ។ ឧទាហរណ៍៖ ${m[2]}`],
  [/^A (\w+) meeting cannot be edited\.$/, (m) => `មិនអាចកែប្រែកិច្ចប្រជុំដែល${st(m[1])}បានទេ។`],
  [/^Cannot add participants to a (\w+) meeting\.$/, (m) => `មិនអាចបន្ថែមអ្នកចូលរួមក្នុងកិច្ចប្រជុំដែល${st(m[1])}បានទេ។`],
  [/^Cannot create a ballot for a (\w+) meeting\.$/, (m) => `មិនអាចបង្កើតការបោះឆ្នោតសម្រាប់កិច្ចប្រជុំដែល${st(m[1])}បានទេ។`],
  [/^Proxies cannot be assigned for a (\w+) meeting\.$/, (m) => `មិនអាចចាត់តាំងអ្នកតំណាងសម្រាប់កិច្ចប្រជុំដែល${st(m[1])}បានទេ។`],
  [/^You cannot request absence for a (\w+) meeting\.$/, (m) => `អ្នកមិនអាចស្នើសុំអវត្តមានសម្រាប់កិច្ចប្រជុំដែល${st(m[1])}បានទេ។`],
  [/^Meeting is already (\w+)\.$/, (m) => `កិច្ចប្រជុំនេះ${st(m[1])}រួចហើយ។`],
  [/^Minutes are (\w+) and can no longer be edited\.$/, (m) => `កំណត់ហេតុប្រជុំ${st(m[1])}ហើយ មិនអាចកែប្រែបានទៀតទេ។`],
  [/^This request is already (\w+)\.$/, (m) => `សំណើនេះ${st(m[1])}រួចហើយ។`],
  [/^Choice must be one of: (.+)\.$/, (m) => `ជម្រើសត្រូវជាមួយក្នុងចំណោម៖ ${m[1]}។`],
  [/^Status must be one of: (.+)\.$/, (m) => `ស្ថានភាពត្រូវជាមួយក្នុងចំណោម៖ ${m[1].split(', ').map(st).join(', ')}។`],
  [/^Agenda item (\d+) does not belong to this meeting\.$/, (m) => `ចំណុចរបៀបវារៈ #${m[1]} មិនមែនជារបស់កិច្ចប្រជុំនេះទេ។`],
  [/^Invalid meeting role '(.+)'\.$/, (m) => `តួនាទីក្នុងប្រជុំ '${m[1]}' មិនត្រឹមត្រូវទេ។`],
  [/^Unknown permission\(s\): (.+)$/, (m) => `មិនស្គាល់សិទ្ធិ៖ ${m[1]}`],
  [/^User (\d+) cannot be invited\.$/, (m) => `មិនអាចអញ្ជើញអ្នកប្រើប្រាស់ #${m[1]} បានទេ។`],
  [/^Reminder sent to (\d+) participants$/, (m) => `បានផ្ញើការរំលឹកទៅអ្នកចូលរួម ${m[1]} នាក់`],
  [/^(.+) not found$/, () => 'រកមិនឃើញទិន្នន័យដែលអ្នកស្វែងរកទេ'],
]

function applyPatterns(list, text) {
  for (const [re, fn] of list) {
    const m = text.match(re)
    if (m) return fn(m)
  }
  return null
}

/** Translate an API message to Khmer; unknown messages are returned unchanged. */
export function serverKm(msg) {
  if (typeof msg !== 'string') return msg
  const text = msg.trim()
  return EXACT[text] || applyPatterns(PATTERNS, text) || msg
}

// ----------------------------------------------------------------- notifications
// Dates in notification bodies look like "20 Nov 2026 09:00 UTC" – kept as they are.
const NOTIF_EXACT = {
  'Welcome to the Boardroom Hub': 'សូមស្វាគមន៍មកកាន់ Boardroom Hub',
  'Your governance workspace is ready.': 'កន្លែងធ្វើការអភិបាលកិច្ចរបស់អ្នករួចរាល់ហើយ។',
  'Minutes awaiting your seal': 'កំណត់ហេតុប្រជុំកំពុងរង់ចាំការបោះត្រារបស់អ្នក',
  'Audit Committee Review minutes were published.': 'កំណត់ហេតុប្រជុំពិនិត្យរបស់គណៈកម្មាធិការសវនកម្ម ត្រូវបានចេញផ្សាយហើយ។',
  'A live vote has opened. Cast your vote now.': 'ការបោះឆ្នោតផ្ទាល់បានបើកហើយ។ សូមបោះឆ្នោតឥឡូវនេះ។',
  'A new version of a board paper is available.': 'មានកំណែថ្មីនៃឯកសារប្រជុំ។',
  'The final minutes are available. The Board Chair will now approve and seal them.': 'កំណត់ហេតុប្រជុំចុងក្រោយអាចមើលបានហើយ។ ប្រធានក្រុមប្រឹក្សាភិបាលនឹងអនុម័ត និងបោះត្រា។',
  'The Board Chair approved and digitally sealed the minutes.': 'ប្រធានក្រុមប្រឹក្សាភិបាលបានអនុម័ត និងបោះត្រាឌីជីថលលើកំណត់ហេតុប្រជុំហើយ។',
  'The host admitted you. Open the meeting page to enter the room.': 'អ្នករៀបចំបានអនុញ្ញាតឱ្យអ្នកចូលហើយ។ សូមបើកទំព័រកិច្ចប្រជុំ ដើម្បីចូលបន្ទប់។',
  'The virtual boardroom is open. Join from the meeting page.': 'បន្ទប់ប្រជុំអនឡាញបានបើកហើយ។ សូមចូលរួមពីទំព័រកិច្ចប្រជុំ។',
}

const OUTCOME = {
  CARRIED: km.voting.carried,
  'NOT CARRIED': km.voting.notCarried,
  'NOT CARRIED – quorum not met': km.voting.notCarriedQuorum,
  'NO DECISION (tie)': km.voting.noDecisionTie,
  'NO DECISION – quorum not met': km.voting.noDecisionQuorum,
}
const outcome = (s) => {
  if (OUTCOME[s]) return OUTCOME[s]
  const d = s.match(/^DECIDED: (.+)$/)
  return d ? km.voting.decided.replace('{option}', km.voting.opt[d[1]] || d[1]) : s
}

const NOTIF_PATTERNS = [
  // titles
  [/^Meeting invitation: (.+)$/s, (m) => `លិខិតអញ្ជើញប្រជុំ៖ ${m[1]}`],
  [/^Rescheduled: (.+)$/s, (m) => `ប្តូរកាលវិភាគ៖ ${m[1]}`],
  [/^Cancelled: (.+)$/s, (m) => `បានលុបចោល៖ ${m[1]}`],
  [/^Live now: (.+)$/s, (m) => `កំពុងប្រជុំឥឡូវនេះ៖ ${m[1]}`],
  [/^Reminder \(24h\): (.+)$/s, (m) => `រំលឹក (មុន 24 ម៉ោង)៖ ${m[1]}`],
  [/^Reminder: (.+)$/s, (m) => `រំលឹក៖ ${m[1]}`],
  [/^Starts within 1 hour: (.+)$/s, (m) => `ចាប់ផ្តើមក្នុងរយៈពេល 1 ម៉ោងទៀត៖ ${m[1]}`],
  [/^Absence request: (.+)$/s, (m) => `សំណើសុំអវត្តមាន៖ ${m[1]}`],
  [/^Absence approved: (.+)$/s, (m) => `អវត្តមានត្រូវបានអនុម័ត៖ ${m[1]}`],
  [/^Absence rejected: (.+)$/s, (m) => `អវត្តមានត្រូវបានបដិសេធ៖ ${m[1]}`],
  [/^Proxy assigned: (.+)$/s, (m) => `បានចាត់តាំងអ្នកតំណាង៖ ${m[1]}`],
  [/^Minutes published: (.+)$/s, (m) => `កំណត់ហេតុប្រជុំបានចេញផ្សាយ៖ ${m[1]}`],
  [/^Minutes sealed: (.+)$/s, (m) => `កំណត់ហេតុប្រជុំបានបោះត្រា៖ ${m[1]}`],
  [/^Vote open: (.+)$/s, (m) => `ការបោះឆ្នោតបានបើក៖ ${m[1]}`],
  [/^Vote closed: (.+)$/s, (m) => `ការបោះឆ្នោតបានបិទ៖ ${m[1]}`],
  [/^Board pack: (.+)$/s, (m) => `ឯកសារប្រជុំ៖ ${m[1]}`],
  [/^Updated: (.+)$/s, (m) => `បានធ្វើបច្ចុប្បន្នភាព៖ ${m[1]}`],
  [/^Late arrival: (.+)$/s, (m) => `មកយឺត៖ ${m[1]}`],
  [/^Early departure: (.+)$/s, (m) => `ចេញមុនម៉ោង៖ ${m[1]}`],
  [/^Waiting room: (.+)$/s, (m) => `បន្ទប់រង់ចាំ៖ ${m[1]}`],
  [/^Admitted to (.+)$/s, (m) => `បានអនុញ្ញាតឱ្យចូល៖ ${m[1]}`],
  // bodies
  [/^You are invited to '(.+)' on (.+?) \(recurring (\w+), (\d+) sessions\)\.$/s,
    (m) => `អ្នកត្រូវបានអញ្ជើញឱ្យចូលរួម '${m[1]}' នៅ ${m[2]} (ប្រជុំ${st(m[3])} ចំនួន ${m[4]} លើក)។`],
  [/^You are invited to '(.+)' on (.+)\.$/s, (m) => `អ្នកត្រូវបានអញ្ជើញឱ្យចូលរួម '${m[1]}' នៅ ${m[2]}។`],
  [/^New time: (.+?) \((\d+) min\)\. Previously (.+)\.$/s, (m) => `ពេលវេលាថ្មី៖ ${m[1]} (${m[2]} នាទី)។ ពេលវេលាចាស់៖ ${m[3]}។`],
  [/^The meeting on (.+?) has been cancelled\. Reason: (.*)$/s,
    (m) => `កិច្ចប្រជុំនៅ ${m[1]} ត្រូវបានលុបចោល។ មូលហេតុ៖ ${m[2] === 'No reason given' ? 'មិនបានបញ្ជាក់មូលហេតុ' : m[2]}`],
  [/^Your meeting is scheduled for (.+)\.$/s, (m) => `កិច្ចប្រជុំរបស់អ្នកត្រូវបានកំណត់នៅ ${m[1]}។`],
  [/^Your meeting starts at (.+)\.$/s, (m) => `កិច្ចប្រជុំរបស់អ្នកចាប់ផ្តើមនៅ ${m[1]}។`],
  [/^(.+) requests absence from '(.+)' \((.+)\)\.$/s, (m) => `${m[1]} ស្នើសុំអវត្តមានពី '${m[2]}' (${reason(m[3])})។`],
  [/^Your absence request was (approved|rejected) by (.+?)\.(?: Comment: (.*))?$/s,
    (m) => `សំណើសុំអវត្តមានរបស់អ្នកត្រូវបាន${m[1] === 'approved' ? 'អនុម័ត' : 'បដិសេធ'}ដោយ ${m[2]}។${m[3] ? ` មតិយោបល់៖ ${m[3]}` : ''}`],
  [/^(.+) will vote on behalf of (.+) at '(.+)' \((.+)\)\.$/s, (m) => `${m[1]} នឹងបោះឆ្នោតជំនួស ${m[2]} នៅ '${m[3]}' (${m[4]})។`],
  [/^A new document was added to '(.+)' for pre-reading\.$/s, (m) => `មានឯកសារថ្មីត្រូវបានបន្ថែមទៅ '${m[1]}' សម្រាប់អានមុនប្រជុំ។`],
  [/^Result: (.+)\.$/s, (m) => `លទ្ធផល៖ ${outcome(m[1])}។`],
  [/^(.+) joined '(.+)' (\d+) minutes after the start\.$/s, (m) => `${m[1]} បានចូល '${m[2]}' យឺត ${m[3]} នាទី ក្រោយម៉ោងចាប់ផ្តើម។`],
  [/^(.+) left '(.+)' before the end\. Voting members still connected: (\d+)\/(\d+)\.$/s,
    (m) => `${m[1]} បានចាកចេញពី '${m[2]}' មុនពេលបញ្ចប់។ សមាជិកមានសិទ្ធិបោះឆ្នោតដែលនៅភ្ជាប់៖ ${m[3]}/${m[4]}។`],
  [/^(.+) is waiting to be admitted\.$/s, (m) => `${m[1]} កំពុងរង់ចាំការអនុញ្ញាតឱ្យចូល។`],
  // security anomaly descriptions
  [/^Blocked attempt to access (.+)$/s, (m) => `បានរារាំងការព្យាយាមចូលប្រើ ${m[1]}`],
  [/^(.+) entered a wrong passcode for '(.+)'$/s, (m) => `${m[1]} បានបញ្ចូលលេខកូដបន្ទប់ខុសសម្រាប់ '${m[2]}'`],
  [/^Account (.+) locked after repeated failed logins$/s, (m) => `គណនី ${m[1]} ត្រូវបានចាក់សោ ដោយសារចូលប្រើខុសច្រើនដង`],
]

/** Translate notification titles/bodies and anomaly descriptions; meeting titles and names stay as typed. */
export function notificationKm(text) {
  if (typeof text !== 'string') return text
  return NOTIF_EXACT[text] || applyPatterns(NOTIF_PATTERNS, text) || text
}
