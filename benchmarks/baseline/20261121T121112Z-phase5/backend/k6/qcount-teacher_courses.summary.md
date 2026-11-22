# k6 summary

scenario: teacher_courses

- http_req_duration: p(99)=46.435, avg=33.331, min=18.601, med=35.485, max=46.867, p(90)=44.386, p(95)=44.710
- http_req_blocked: avg=0.018, min=0.004, med=0.011, max=0.138, p(90)=0.016, p(95)=0.026, p(99)=0.115
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: med=35.485, max=46.867, p(90)=44.386, p(95)=44.710, p(99)=46.435, avg=33.331, min=18.601
- http_req_receiving: p(99)=0.173, avg=0.056, min=0.034, med=0.047, max=0.198, p(90)=0.066, p(95)=0.075
- iterations: count=20.000, rate=4.268
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- vus: min=1.000, max=1.000
- http_req_connecting: max=0.098, p(90)=0.000, p(95)=0.005, p(99)=0.079, avg=0.005, min=0.000, med=0.000
- http_req_waiting: avg=33.233, min=18.535, med=35.396, max=46.617, p(90)=44.286, p(95)=44.602, p(99)=46.214
- http_req_sending: p(90)=0.052, p(95)=0.056, p(99)=0.060, avg=0.042, min=0.013, med=0.043, max=0.061
