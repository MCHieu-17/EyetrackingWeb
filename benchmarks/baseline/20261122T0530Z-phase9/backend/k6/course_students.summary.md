# k6 summary

scenario: course_students

- http_req_connecting: min=0.000, med=0.000, max=0.102, p(90)=0.000, p(95)=0.000, p(99)=0.101, avg=0.002
- http_req_duration: min=2.464, med=8.346, max=71.297, p(90)=15.048, p(95)=15.683, p(99)=37.484, avg=10.236
- http_req_waiting: p(95)=15.255, p(99)=37.362, avg=9.960, min=2.230, med=8.138, max=71.221, p(90)=14.522
- vus: min=5.000, max=5.000
- iterations: count=238.000, rate=23.624
- http_req_receiving: avg=0.237, min=0.019, med=0.135, max=2.294, p(90)=0.407, p(95)=0.505, p(99)=2.169
- http_req_failed: rate=0.000
- http_req_sending: med=0.040, max=0.160, p(90)=0.049, p(95)=0.051, p(99)=0.068, avg=0.040, min=0.008
- http_req_duration{expected_response:true}: min=2.464, med=8.346, max=71.297, p(90)=15.048, p(95)=15.683, p(99)=37.484, avg=10.236
- http_req_blocked: med=0.011, max=0.161, p(90)=0.014, p(95)=0.015, p(99)=0.132, avg=0.014, min=0.002
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
