# k6 summary

scenario: course_visits

- http_req_duration: avg=13.917, min=3.123, med=13.139, max=64.116, p(90)=19.397, p(95)=19.773, p(99)=57.109
- http_req_receiving: min=0.043, med=0.235, max=2.829, p(90)=0.572, p(95)=1.841, p(99)=2.644, avg=0.378
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_sending: avg=0.043, min=0.008, med=0.041, max=0.397, p(90)=0.052, p(95)=0.056, p(99)=0.186
- vus: min=5.000, max=5.000
- iterations: count=235.000, rate=23.041
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.086, avg=0.002, min=0.000, med=0.000, max=0.090
- http_req_blocked: p(99)=0.128, avg=0.014, min=0.002, med=0.011, max=0.140, p(90)=0.013, p(95)=0.015
- http_req_failed: rate=0.000
- http_req_waiting: avg=13.496, min=3.008, med=12.729, max=63.894, p(90)=19.132, p(95)=19.532, p(99)=56.837
- http_req_duration{expected_response:true}: max=64.116, p(90)=19.397, p(95)=19.773, p(99)=57.109, avg=13.917, min=3.123, med=13.139
