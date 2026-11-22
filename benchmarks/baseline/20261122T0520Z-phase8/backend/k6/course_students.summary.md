# k6 summary

scenario: course_students

- http_req_failed: rate=0.000
- http_req_blocked: min=0.003, med=0.012, max=0.117, p(90)=0.019, p(95)=0.024, p(99)=0.090, avg=0.015
- http_req_receiving: avg=0.071, min=0.022, med=0.066, max=0.171, p(90)=0.105, p(95)=0.113, p(99)=0.158
- http_req_connecting: p(99)=0.065, avg=0.002, min=0.000, med=0.000, max=0.082, p(90)=0.000, p(95)=0.000
- http_req_sending: min=0.011, med=0.044, max=0.073, p(90)=0.053, p(95)=0.055, p(99)=0.061, avg=0.043
- http_req_waiting: med=43.652, max=69.129, p(90)=50.637, p(95)=51.379, p(99)=62.641, avg=39.004, min=21.965
- vus: min=2.000, max=2.000
- http_req_duration: min=22.021, med=43.769, max=69.245, p(90)=50.743, p(95)=51.515, p(99)=62.737, avg=39.118
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- iterations: count=84.000, rate=8.331
- http_req_duration{expected_response:true}: p(95)=51.515, p(99)=62.737, avg=39.118, min=22.021, med=43.769, max=69.245, p(90)=50.743
