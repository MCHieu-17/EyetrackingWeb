# k6 summary

scenario: course_visits

- http_req_waiting: p(90)=13.197, p(95)=13.833, p(99)=22.217, avg=8.863, min=1.939, med=8.431, max=26.976
- http_req_duration: avg=9.073, min=2.014, med=8.674, max=27.054, p(90)=13.543, p(95)=14.085, p(99)=22.307
- http_req_failed: rate=0.000
- iterations: rate=23.564, count=240.000
- http_req_receiving: avg=0.169, min=0.015, med=0.127, max=1.017, p(90)=0.335, p(95)=0.421, p(99)=0.585
- http_req_blocked: p(95)=0.015, p(99)=0.114, avg=0.013, min=0.002, med=0.011, max=0.126, p(90)=0.014
- http_req_connecting: avg=0.002, min=0.000, med=0.000, max=0.087, p(90)=0.000, p(95)=0.000, p(99)=0.083
- http_req_sending: avg=0.041, min=0.006, med=0.041, max=0.095, p(90)=0.053, p(95)=0.062, p(99)=0.084
- http_req_duration{expected_response:true}: min=2.014, med=8.674, max=27.054, p(90)=13.543, p(95)=14.085, p(99)=22.307, avg=9.073
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- vus: max=5.000, min=5.000
